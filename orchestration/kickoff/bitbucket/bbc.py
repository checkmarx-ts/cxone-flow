from .bb_base import AbstractBitBucketKickoffOrchestrator
from orchestration.naming import BitbucketCloudProjectNaming
from cxoneflow_kickoff_api import BitbucketCloudKickoffMsg


class BitBucketCloudKickoffOrchestrator(AbstractBitBucketKickoffOrchestrator):

    def __init__(self, msg: BitbucketCloudKickoffMsg, *args, **kwargs):
        self.__msg = msg
        super().__init__(*args, **kwargs)

    @property
    def config_key(self):
        return "bbc"

    @property
    def kickoff_msg(self) -> BitbucketCloudKickoffMsg:
        return self.__msg

    @property
    def _repo_organization(self) -> str:
        return self.kickoff_msg.workspace_name

    async def get_default_cxone_project_name(self) -> str:
        return BitbucketCloudProjectNaming.create_project_name(
            self._repo_organization,
            self._repo_project_key,
            self.kickoff_msg.project_name,
            self._repo_slug,
        )
