from .basic import ADOEServiceBasic
from cxone_api.util import json_on_ok
from api_utils.apisession import SCMAuthException
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
from typing import Dict
from jsonpath_ng import parse
from jsonpath_ng.ext import parser
import json


class ADOEServiceChecks(ADOEServiceBasic):

  __pr_iteration_hash = parse("$.resource.lastMergeSourceCommit.commitId")

  __MAX_CHECK_STRING_LEN = 128

  def __init__(self, check_name : str, check_genre : str, **kwargs):
    ADOEServiceBasic.__init__(self, **kwargs)
    self.__check_name = check_name
    self.__check_genre = check_genre

  def __get_check_name(self):
    return f"{self.__check_genre + '/' if self.__check_genre is not None else ''}{self.__check_name}"

  def __make_payload(self, state : str, scan_url : str, msg : str, iteration : int) -> Dict:
     return {
      "iterationId" : iteration,
      "state": state,
      "description": f"{self.__get_check_name()}: {msg}",
      "context": {
        "name": self.__check_name,
        "genre" : self.__check_genre
      },
    } | {"targetUrl" : scan_url} if scan_url is not None else {}

  async def __get_iteration(self, pr_details : PRDetails) -> int:
    iteration_list_api_url = f"/{pr_details.organization}/{pr_details.repo_project}/_apis/git/repositories/{pr_details.repo_slug}/pullRequests/{pr_details.pr_id}/iterations?api-version=7.1"
    
    iterations_list = json_on_ok(await self.exec("GET", iteration_list_api_url))

    iteration_target_hash = ADOEServiceChecks.__pr_iteration_hash.find(pr_details.event_context.message).pop().value
    matching_iteration_list = parser.parse(f"$.value[?(@.sourceRefCommit.commitId == \"{iteration_target_hash}\")].id").find(iterations_list)

    if len(matching_iteration_list) > 0:
      return matching_iteration_list.pop().value
    else:
      # Minimum iteration value; this return will likely never be invoked.
      return 1

  async def __set_check_status(self, pr_details : PRDetails, state : str, scan_url : str = None, msg : str = None):

    status_create_api_url = f"/{pr_details.organization}/{pr_details.repo_project}/_apis/git/repositories/{pr_details.repo_slug}/pullRequests/{pr_details.pr_id}/statuses?api-version=7.1"

    try:
      resp = await self.exec("POST", status_create_api_url,
                            extra_headers={"Content-Type" : "application/json"},
                            body=json.dumps(self.__make_payload(state, scan_url, msg, await self.__get_iteration(pr_details))))

      if not resp.ok:
        ADOEServiceChecks.log().error("Attempt to update check " + 
                                      f"{self.__get_check_name()} at {status_create_api_url} " +
                                      f"failed with response: {resp.status_code}: {resp.text}")
    except SCMAuthException:
        ADOEServiceChecks.log().warning(f"Could not create status, permissions for Code:R+W are required to update status checks: {status_create_api_url}")

  
  async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "pending", content.scan_url, content.get_status_msg(ADOEServiceChecks.__MAX_CHECK_STRING_LEN))
    return await super().exec_pr_scan_update_decorate(pr_details, content, scan_details)
    
  async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
    await self.__set_check_status(pr_details, "pending", content.scan_url, msg=content.get_status_msg(ADOEServiceChecks.__MAX_CHECK_STRING_LEN))
    return await super().exec_pr_scan_pending_decorate(pr_details, content)

  async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "failed", content.scan_url, content.get_status_msg(ADOEServiceChecks.__MAX_CHECK_STRING_LEN))
    return await super().exec_pr_scan_failure_decorate(pr_details, content, scan_details)
  
  async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__set_check_status(pr_details, "succeeded", content.scan_url, content.get_status_msg(ADOEServiceChecks.__MAX_CHECK_STRING_LEN))
    return await super().exec_pr_scan_success_decorate(pr_details, content, scan_details)
  
  async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
    await self.__set_check_status(pr_details, "error", msg=fail_msg)
    return await super().exec_pr_unrecoverable_error(pr_details, scan_details, fail_msg)
  