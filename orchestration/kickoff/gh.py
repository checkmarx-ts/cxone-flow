from orchestration.kickoff import KickoffOrchestrator
from cxoneflow_kickoff_api import GithubKickoffMsg
from orchestration.naming.gh import GithubProjectNaming
from scm_services import SCMService
from scm_services.cloner import CloneWorker

class GithubKickoffOrchestrator(KickoffOrchestrator):

  def __init__(self, msg : GithubKickoffMsg, *args, **kwargs):
     self.__msg = msg
     super().__init__(*args, **kwargs)

  @property
  def config_key(self):
      return "gh"

  @property
  def route_urls(self) -> list:
      return self.kickoff_msg.clone_urls

  @property
  def kickoff_msg(self) -> GithubKickoffMsg:
     return self.__msg

  async def get_cxone_project_name(self) -> str:
    return GithubProjectNaming.create_project_name(
       self.kickoff_msg.repo_organization_name, self.kickoff_msg.repo_name)
  
  async def _get_clone_worker(self, scm_service : SCMService, clone_url : str, failures : int) -> CloneWorker:
    return await scm_service.cloner.clone(clone_url, self.event_context, failures > 0)


