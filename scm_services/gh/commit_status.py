from scm_services.gh.abstract import AbstractGHService
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
import json

class GHServiceCommitStatus(AbstractGHService):

    __status_msg_max = 64

    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        # pending status

        head_sha = self._get_head_sha(pr_details)
        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/statuses/{head_sha}"

        body = {
            "state" : "pending",
            "target_url" : content.scan_url,
            "description" : content.get_status_msg(GHServiceCommitStatus.__status_msg_max),
            "context" : "checkmarx"
        }

        # TODO: error handling
        r = await self.exec("POST", url, body = json.dumps(body),
                                extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                event_context=pr_details.event_context)

    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        return await self.exec_pr_scan_update_decorate(pr_details, content, None)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        head_sha = self._get_head_sha(pr_details)
        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/statuses/{head_sha}"

        body = {
            "state" : "error",
            "target_url" : content.scan_url,
            "description" : content.get_status_msg(GHServiceCommitStatus.__status_msg_max),
            "context" : "checkmarx"
        }

        # TODO: error handling
        r = await self.exec("POST", url, body = json.dumps(body),
                                extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                event_context=pr_details.event_context)
        

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        head_sha = self._get_head_sha(pr_details)
        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/statuses/{head_sha}"

        body = {
            "state" : "success",
            "target_url" : content.scan_url,
            "description" : content.get_status_msg(GHServiceCommitStatus.__status_msg_max),
            "context" : "checkmarx"
        }

        # TODO: error handling
        r = await self.exec("POST", url, body = json.dumps(body),
                                extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                event_context=pr_details.event_context)

