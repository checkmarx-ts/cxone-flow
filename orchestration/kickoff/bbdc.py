from orchestration.kickoff import KickoffOrchestrator
from cxoneflow_kickoff_api import BitbucketKickoffMsg
from orchestration.naming.bbdc import BitbucketProjectNaming

class BitBucketDataCenterKickoffOrchestrator(KickoffOrchestrator):

    def __init__(self, msg : BitbucketKickoffMsg, *args, **kwargs):
        self.__msg = msg
        super().__init__(*args, **kwargs)

    @property
    def config_key(self):
        return "bbdc"

    @property
    def route_urls(self) -> list:
        return self.kickoff_msg.clone_urls

    @property
    def kickoff_msg(self) -> BitbucketKickoffMsg:
        return self.__msg

    @property
    def _repo_project_key(self) -> str:
        return self.__msg.project_key

    @property
    def _repo_organization(self) -> str:
        return self._repo_project_key

    @property
    def _repo_slug(self) -> str:
        return self._repo_name

    @property
    def _repo_name(self) -> str:
        return self.__msg.repo_name

    async def get_default_cxone_project_name(self) -> str:
        return BitbucketProjectNaming.create_project_name(self.kickoff_msg.project_key, 
                                                        self.kickoff_msg.project_name, 
                                                        self.kickoff_msg.repo_name)

