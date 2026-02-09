from scm_services.gh.basic import GHServiceBasic
from scm_services.policy import PolicyProperties
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
from cxone_api.util import json_on_ok
from typing import Dict
import json

class GHServiceCommitStatus(GHServiceBasic, PolicyProperties):

    __status_msg_max = 64

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __make_payload(self, state : str, content : PullRequestCommentContent) -> Dict:
        return {
            "state" : state,
            "target_url" : content.scan_url,
            "description" : content.get_status_msg(GHServiceCommitStatus.__status_msg_max),
            "context" : self.check_name
        }

    def __make_plaintext_payload(self, state : str, content : str) -> Dict:
        return {
            "state" : state,
            "target_url" : None,
            "description" : content,
            "context" : self.check_name
        }

    def __make_api_url(self, pr_details : PRDetails) -> str:
        return f"/repos/{pr_details.organization}/{pr_details.repo_slug}/statuses/{self._get_head_sha(pr_details)}"
    
    async def __post_update(self, pr_details : PRDetails, update_body : Dict):
        api_url = self.__make_api_url(pr_details)
        return await self.exec("POST", api_url, 
                            body = json.dumps(update_body),
                            extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                            event_context=pr_details.event_context)
    
    async def __update_status(self, state : str,  pr_details : PRDetails, content : PullRequestCommentContent) -> None:
        api_url = self.__make_api_url(pr_details)
        resp = await self.__post_update(pr_details, self.__make_payload(state, content))

        if not resp.ok:
            GHServiceCommitStatus.log().error("Commit status update failed: %s returned %d:%s", api_url, resp.status_code, resp.text)
        else:
            GHServiceCommitStatus.log().debug("Commit status updated: %s: %s", api_url, json_on_ok(resp))

    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        await self.__update_status("pending", pr_details, content)
        await super().exec_pr_scan_update_decorate(pr_details, content, scan_details)
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        await self.__update_status("pending", pr_details, content)
        await super().exec_pr_scan_pending_decorate(pr_details, content)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        await self.__update_status("error", pr_details, content)
        await super().exec_pr_scan_failure_decorate(pr_details, content, scan_details)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        await self.__update_status("success", pr_details, content)
        await super().exec_pr_scan_success_decorate(pr_details, content, scan_details)

    async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
        await self.__post_update(pr_details, self.__make_plaintext_payload("error", fail_msg))
