from scm_services import SCMService
from api_utils.auth_factories import EventContext
from typing import Coroutine, Tuple
import logging

class ProjectNamingService:

  CORO_SPEC = Coroutine[None, Tuple[EventContext, SCMService], str]

  @staticmethod
  def log():
      return logging.getLogger("ProjectNamingService")

  def __init__(self, coro : CORO_SPEC, scm_service : SCMService):
    self.__naming_coro = coro
    self.__scm_service = scm_service

  
  async def get_project_name(self, default_name : str, context : EventContext) -> str:
    if self.__naming_coro is None:
      return default_name
    
    try:
      name = await self.__naming_coro(context, self.__scm_service)
      return name if name is not None else default_name
    except BaseException as ex:
      ProjectNamingService.log().info(f"Exception thrown by naming module [{self.__naming_coro.__name__}].  Using default name [{default_name}].")
      ProjectNamingService.log().exception(ex)
      return default_name
