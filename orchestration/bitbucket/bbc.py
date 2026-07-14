import urllib3
from jsonpath_ng.ext.parser import parse
from typing import Dict, List
from orchestration.naming import BitbucketCloudProjectNaming
from cxone_api.util import json_on_ok
from orchestration.exceptions import OrchestrationException
from .bbbase import BitBucketAbstractOrchestrator
from api_utils.auth_factories import EventContext
from services import CxOneFlowServices, SCMService

class BitBucketCloudOrchestrator(BitBucketAbstractOrchestrator):
  
  __route_urls_query = parse("$.repository.links.html.href")
  __repo_full_name_query = parse("$.repository.full_name")
  __repo_project_name_query = parse("$.repository.project.name")
  __repo_project_key_query = parse("$.repository.project.key")
  __clone_urls_query = parse("$.links.clone[*]")
  __repo_workspace_slug_query = parse("$.repository.workspace.slug")

  __first_push_commit_query = parse("$.push.changes[?(@.new.target.type=='commit')]")

  __branchmodel_name_query = parse("$..['development','production'].branch.name")


  def __init__(self, event_context : EventContext):
    BitBucketAbstractOrchestrator.__init__(self, event_context)

    self.__clone_urls = {}

    self.__route_urls = [url.value for url in BitBucketCloudOrchestrator.__route_urls_query.find(self.event_context.message)]

    if len(self.__route_urls) == 0:
       raise OrchestrationException("Route URLs could not be found in the payload.")

    pass

  @property
  def config_key(self):
    return "bbc"

  @property
  def route_urls(self) -> list:
      return self.__route_urls

  @property
  def is_diagnostic(self) -> bool:
      return False
  
  def _repo_clone_url(self, cloner) -> str:
      return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]
      
  async def _get_target_branch_and_hash(self) -> tuple:
      return self.__target_branch, self.__target_hash

  async def _get_source_branch_and_hash(self) -> tuple:
      return self.__source_branch, self.__source_hash

  async def _get_protected_branches(self, scm_service : SCMService) -> List:
    branchmodel_config = json_on_ok(await scm_service.exec("GET", f"/repositories/{self._repo_organization}/{self._repo_slug}/effective-branching-model"))
    return list(set([name.value for name in BitBucketCloudOrchestrator.__branchmodel_name_query.find(branchmodel_config)]))

  def __init_clone_urls(self, repo_data : Dict) -> None:
    for clone_entry in BitBucketCloudOrchestrator.__clone_urls_query.find(repo_data):
      name = clone_entry.value.get("name")
      if name is not None:
        if name.lower().startswith("http"):
          # Normalize by removing the auth part since that is provided in the config and reformed
          # for clone/api requests.
          href = urllib3.util.parse_url(clone_entry.value.get("href"))
          self.__clone_urls[name] = str(urllib3.util.Url(scheme = href.scheme,
                                                          host=href.host,
                                                          port=href.port,
                                                          path=href.path,
                                                          query=href.query,
                                                          fragment=href.fragment))
        else:
          self.__clone_urls[name] = clone_entry.value.get("href")

  async def execute(self, services : CxOneFlowServices):
      if self.event_name not in BitBucketCloudOrchestrator.__workflow_map.keys():
          BitBucketCloudOrchestrator.log().error(f"Unhandled event type: {self.event_name}")
          return 
      else:
          return await BitBucketCloudOrchestrator.__workflow_map[self.event_name](self, services)

  async def handle_delegated_scan(self, services : CxOneFlowServices, scan_id : str):
    raise NotImplementedError("handle_delegated_scan")
      # self.delegated_scan = True
      # return await self.__delegated_dispatcher(BitBucketDataCenterOrchestrator.__delegate_scan_handler_map, services, scan_id)

  async def __populate_common_push_data(self, commit_dict : Dict, scm_service : SCMService):
      self.__source_branch = self.__target_branch = None
      self.__source_hash = self.__target_hash = None

      new_commit = commit_dict.get("new")
      self.__source_branch = self.__target_branch = new_commit.get("name")
      self.__source_hash = self.__target_hash = new_commit.get("target").get("hash")

      self._repo_project_key = BitBucketCloudOrchestrator.__repo_project_key_query.find(self.event_context.message).pop().value
      self._repo_project_name = BitBucketCloudOrchestrator.__repo_project_name_query.find(self.event_context.message).pop().value
      self._repo_name = BitBucketCloudOrchestrator.__repo_full_name_query.find(self.event_context.message).pop().value
      self._repo_organization = BitBucketCloudOrchestrator.__repo_workspace_slug_query.find(self.event_context.message).pop().value

      repo_data = json_on_ok(await scm_service.exec("GET", f"repositories/{self._repo_name}"))
      self._repo_slug = repo_data.get("slug")
      self.__init_clone_urls(repo_data)


  async def _execute_push_scan_workflow(self, services : CxOneFlowServices):
      found_first_commit = BitBucketCloudOrchestrator.__first_push_commit_query.find(self.event_context.message)
      if len(found_first_commit) > 0:
        first_commit = found_first_commit.pop().value

        await self.__populate_common_push_data(first_commit, services.scm)
        return await BitBucketAbstractOrchestrator._execute_push_scan_workflow(self, services)
      else:
         BitBucketCloudOrchestrator.log().info("No commits found to handle.")

  async def get_default_cxone_project_name(self) -> str:
     return BitbucketCloudProjectNaming.create_project_name(self._repo_organization, self._repo_project_key, self._repo_project_name, self._repo_slug)
  
  __workflow_map = {
    "repo:push" : _execute_push_scan_workflow,
  }
  __delegate_scan_handler_map = {}