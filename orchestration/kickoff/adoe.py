from . import KickoffOrchestrator
from cxoneflow_kickoff_api import AdoKickoffMsg
from orchestration.naming.adoe import AzureDevOpsProjectNaming

class AzureDevOpsKickoffOrchestrator(KickoffOrchestrator):

  def __init__(self, msg : AdoKickoffMsg, *args, **kwargs):
     self.__msg = msg
     super().__init__(*args, **kwargs)

  @property
  def config_key(self):
      return "adoe"

  @property
  def route_urls(self) -> list:
      return self.kickoff_msg.clone_urls

  @property
  def kickoff_msg(self) -> AdoKickoffMsg:
     return self.__msg

  async def get_cxone_project_name(self) -> str:
    return AzureDevOpsProjectNaming.create_project_name(self.kickoff_msg.collection_name,
                                                        self.kickoff_msg.project_name, self.kickoff_msg.repo_name)
  
