from orchestration.kickoff.ko_orch import KickoffOrchestrator


class AbstractBitBucketKickoffOrchestrator(KickoffOrchestrator):

    @property
    def route_urls(self) -> list:
        return self.kickoff_msg.clone_urls

    @property
    def _repo_project_key(self) -> str:
        return self.kickoff_msg.project_key

    @property
    def _repo_slug(self) -> str:
        return self._repo_name

    @property
    def _repo_name(self) -> str:
        return self.kickoff_msg.repo_name
