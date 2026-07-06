from .basic import ADOEServiceBasic
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
from typing import Dict
import json


class ADOEServiceChecks(ADOEServiceBasic):

  def __init__(self, check_name : str, check_genre : str, **kwargs):
    ADOEServiceBasic.__init__(self, **kwargs)
    self.__check_name = check_name
    self.__check_genre = check_genre

  def __make_payload(self, state : str, scan_url : str, msg = "Scan executing") -> Dict:
     return {
      "state": state,
      "description": msg,
      "context": {
        "name": self.__check_name,
        "genre" : self.__check_genre
      },
    } | {"targetUrl" : scan_url} if scan_url is not None else {}

  async def __set_check_status(self, pr_details : PRDetails, state : str, scan_url : str = None, msg : str = None):
    url = f"/{pr_details.organization}/{pr_details.repo_project}/_apis/git/repositories/{pr_details.repo_slug}/pullRequests/{pr_details.pr_id}/statuses?api-version=7.1"

    resp = await self.exec("POST", url,
                           extra_headers={"Content-Type" : "application/json"},
                           body=json.dumps(self.__make_payload(state, scan_url)))

    if not resp.ok:
       ADOEServiceChecks.log().error("Attempt to update check " + 
                                     f"{self.__check_genre + '/' if self.__check_genre is not None else ''}{self.__check_name} at {url} " +
                                     f"failed with response: {resp.status_code}: {resp.text}")
  
  async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "pending", content.scan_url)
    return await super().exec_pr_scan_update_decorate(pr_details, content, scan_details)
    
  async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
    await self.__set_check_status(pr_details, "pending", content.scan_url, msg=content.get_status_msg(128))
    return await super().exec_pr_scan_pending_decorate(pr_details, content)

  async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "failed", content.scan_url)
    return await super().exec_pr_scan_failure_decorate(pr_details, content, scan_details)
  
  async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "succeeded", content.scan_url)
    return await super().exec_pr_scan_success_decorate(pr_details, content, scan_details)
  
  async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
    await self.__set_check_status(pr_details, "error", msg=fail_msg)
    return await super().exec_pr_unrecoverable_error(pr_details, scan_details, fail_msg)
  