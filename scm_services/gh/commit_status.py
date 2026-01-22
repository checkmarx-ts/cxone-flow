from scm_services.gh.abstract import AbstractGHService
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage

class GHServiceCommitStatus(AbstractGHService):


    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_update_decorate")
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        raise NotImplementedError("exec_pr_scan_pending_decorate")

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_failure_decorate")

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_success_decorate")

