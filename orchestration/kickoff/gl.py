from . import KickoffOrchestrator
from cxoneflow_kickoff_api import GitlabKickoffMsg
from orchestration.naming.gl import GitlabProjectNaming

class GitlabKickoffOrchestrator(KickoffOrchestrator):

  def __init__(self, msg : GitlabKickoffMsg, *args, **kwargs):
     self.__msg = msg
     super().__init__(*args, **kwargs)

  @property
  def config_key(self):
      return "gl"

  @property
  def route_urls(self) -> list:
      return self.kickoff_msg.clone_urls

  @property
  def kickoff_msg(self) -> GitlabKickoffMsg:
     return self.__msg

  async def get_cxone_project_name(self) -> str:
    return GitlabProjectNaming.create_project_name(self.kickoff_msg.repo_path_with_namespace)
