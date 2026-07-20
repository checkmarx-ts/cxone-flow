from .bb_base import AbstractBitBucketKickoffOrchestrator
from cxoneflow_kickoff_api import BitbucketDCKickoffMsg
from orchestration.naming import BitbucketDCProjectNaming

class BitBucketDataCenterKickoffOrchestrator(AbstractBitBucketKickoffOrchestrator):

  def __init__(self, msg : BitbucketDCKickoffMsg, *args, **kwargs):
      self.__msg = msg
      super().__init__(*args, **kwargs)

  @property
  def config_key(self):
      return "bbdc"

  @property
  def kickoff_msg(self) -> BitbucketDCKickoffMsg:
      return self.__msg

  @property
  def _repo_organization(self) -> str:
      return self._repo_project_key

  async def get_default_cxone_project_name(self) -> str:
      return BitbucketDCProjectNaming.create_project_name(self.kickoff_msg.project_key, 
                                                      self.kickoff_msg.project_name, 
                                                      self.kickoff_msg.repo_name)

