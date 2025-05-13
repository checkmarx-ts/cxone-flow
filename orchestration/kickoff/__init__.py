from orchestration import OrchestratorBase
import cxoneflow_kickoff_api as ko
from kickoff_services import KickoffService
from typing import Union, Dict, List
from services import CxOneFlowServices
from scm_services import SCMService
from scm_services.cloner import Cloner
import logging, re




class KickoffOrchestrator(OrchestratorBase):
  class KickoffScanExistsException(BaseException):...
  class TooManyRunningScansExeception(BaseException):...

  __HTTP_CLONE_PATTERN = re.compile("^http.*")

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__started_scan = None
    self.__executing_scans = []

    self.__clone_urls = {}
    for url in self.kickoff_msg.clone_urls:
      if KickoffOrchestrator.__HTTP_CLONE_PATTERN.match(url):
        self.__clone_urls['http'] = url
      else:
         self.__clone_urls['ssh'] = url
             
  @classmethod
  def log(clazz) -> logging.Logger:
      return logging.getLogger(clazz.__name__)

  @staticmethod
  def __get_auth_bearer_token(headers : Dict) -> Union[str,None]:
      token = None

      if 'Authorization' in headers.keys():
          content = headers['Authorization'].split(" ")
          content.reverse()

          if content.pop().lower() == "bearer":
              token = content.pop()

      return token
  
  @property
  def kickoff_msg(self) -> ko.KickoffMsg:
     raise NotImplementedError("kickoff_msg")

  async def valid_bearer_token(self, ko_service : KickoffService) -> bool:
     token = KickoffOrchestrator.__get_auth_bearer_token(self.event_context.headers)
     return await ko_service.validate_jwt(token)

  @property
  def event_name(self) -> str:
      return "kickoff"

  async def _get_target_branch_and_hash(self) -> tuple:
      return await self._get_source_branch_and_hash()

  async def _get_source_branch_and_hash(self) -> tuple:
      return self.kickoff_msg.branch_name, self.kickoff_msg.sha

  async def _get_protected_branches(self, scm_service : SCMService) -> list:
      return [KickoffOrchestrator.normalize_branch_name(self.kickoff_msg.branch_name)]

  def _repo_clone_url(self, cloner : Cloner) -> str:
      return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]

  @property
  def started_scan(self) -> ko.ExecutingScan:
     return self.__started_scan

  @property
  def running_scans(self) -> List[ko.ExecutingScan]:
     return self.__executing_scans
  
  async def execute(self, services : CxOneFlowServices) -> bool:

    self.__executing_scans = await services.kickoff.get_running_ko_scans()

    target_branch, _ = await self._get_target_branch_and_hash()
    project_name = await services.naming.get_project_name(await self.get_default_cxone_project_name(), self.event_context)

    if await services.kickoff.one_scan_exists_on_branch(project_name, target_branch):
       raise KickoffOrchestrator.KickoffScanExistsException()

    if len(self.running_scans) >= services.kickoff.max_concurrent_scans:
       raise KickoffOrchestrator.TooManyRunningScansExeception()

    completed = await services.kickoff.get_completed_ko_scans_by_project(project_name)
    if len(completed) >= 1:
       raise KickoffOrchestrator.KickoffScanExistsException()

    inspector, action = await self._execute_push_scan_workflow(services, scan_tags = services.kickoff.scan_tag_dict)

    self.__started_scan = ko.ExecutingScan(project_name, inspector.project_id, inspector.scan_id, target_branch)

    return action == OrchestratorBase.ScanAction.EXECUTING


