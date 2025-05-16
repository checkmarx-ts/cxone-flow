from cxone_api import CxOneClient
from cxone_api.low.access_mgmt.user_mgmt import retrieve_groups
from cxone_api.util import page_generator, json_on_ok
from typing import List
from collections import namedtuple
import asyncio, re, logging

class GroupingService:

  Route = namedtuple("Route", ['regex', 'groups'])
  
  __MAX_RESOLUTION_ERRORS = 3

  @staticmethod
  def log():
      return logging.getLogger("GroupingService")

  def __init__(self, client : CxOneClient):
    self.__client = client
    self.__lock = asyncio.Lock()
    self.__routes = []
    self.__groupid_index = {}
    self.__path_res_errors = {}

  def add_assignment_rule(self, clone_url_regex : str, group_paths : List[str]) -> None:
    self.__routes.append(GroupingService.Route(re.compile(clone_url_regex), [x.lstrip("/") for x in group_paths]))

  async def __increment_error(self, group_path : str):
    if group_path in self.__path_res_errors.keys():
      self.__path_res_errors[group_path] += 1
    else:
      self.__path_res_errors[group_path] = 1

  async def __resolve_group_ids(self, group_paths : List[str]) -> List[str]:
    resolved_ids = []
    for path in group_paths:
      async with self.__lock:
        if path not in self.__groupid_index.keys():
          
          if path in self.__path_res_errors.keys() and \
            self.__path_res_errors[path] > GroupingService.__MAX_RESOLUTION_ERRORS:
            GroupingService.log().warning(f"Group ID resolution for group {path} has failed to resolve in the last" + 
                                          f" {self.__path_res_errors[path]} attempts. The group may not be valid.")

          try:
            group_defs = json_on_ok(await retrieve_groups(self.__client, search=path))

            # returning no groups is actually an error
            if len(group_defs) == 0:
              await self.__increment_error(path)
              continue

            for gdef in group_defs:
              if gdef['name'] == path:
                self.__groupid_index[path] = gdef['id']
                break
          except BaseException as ex:
            await self.__increment_error(path)
            GroupingService.log().exception(f"Exception trying to resolve id for group [{path}]", ex)

        # It is possible the group id was not resolved, so check before
        # trying to add the group id.
        if path in self.__groupid_index.keys():
          resolved_ids.append(self.__groupid_index[path])
          
          if path in self.__path_res_errors.keys():
            del self.__path_res_errors[path]

    return resolved_ids

  async def resolve_groups(self, clone_url : str) -> List[str]:
    resolved = []

    for route in self.__routes:
      if route.regex.match(clone_url):
        resolved = resolved + await self.__resolve_group_ids(route.groups)

    return resolved
  
  async def purge_cache(self) -> None:
    async with self.__lock:
      self.__groupid_index = {}
      self.__path_res_errors = {}

