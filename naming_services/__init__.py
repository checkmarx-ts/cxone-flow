from scm_services import SCMService
from api_utils.auth_factories import EventContext
from typing import Coroutine, Tuple
from time import perf_counter_ns
import logging, contextlib

class ProjectNamingService:

  CORO_SPEC = Coroutine[None, Tuple[EventContext, SCMService], str]

  @staticmethod
  def log():
      return logging.getLogger("ProjectNamingService")

  def __init__(self, coro : CORO_SPEC, scm_service : SCMService):
    self.__naming_coro = coro
    self.__scm_service = scm_service


  @contextlib.asynccontextmanager
  async def __call_timer(self):
    start = perf_counter_ns()

    try:
      yield start
    finally:
      ProjectNamingService.log().info(f"{self.__naming_coro.__module__}.{self.__naming_coro.__name__} script execution time: {perf_counter_ns() - start}ns")
      

  
  async def get_project_name(self, default_name : str, context : EventContext) -> str:
    if self.__naming_coro is None:
      return default_name

    async with self.__call_timer():  
      try:
        name = await self.__naming_coro(context, self.__scm_service)
        if name is None:
          ProjectNamingService.log().warning(f"Naming module [{self.__naming_coro.__name__}] returned None, using default name {default_name}.")
        return name if name is not None else default_name
      except BaseException as ex:
        ProjectNamingService.log().info(f"Exception thrown by naming module [{self.__naming_coro.__name__}].  Using default name [{default_name}].")
        ProjectNamingService.log().exception(ex)
        return default_name
