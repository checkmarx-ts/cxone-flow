from .scm import SCMService
from api_utils.auth_factories import EventContext
from api_utils.pagers import async_api_page_generator
from api_utils import form_url
from requests import Response
from workflows.pr_content import PullRequestAbstractMarkdownComment
from workflows.messaging import PRDetails, ScanMessage
from cxone_api.util import json_on_ok
from workflows.pr_content import PullRequestCommentContent
from api_utils.apisession import SCMAuthException
import json
from jsonpath_ng.ext import parser
from jsonpath_ng import parse
from typing import Union, Dict
from enum import Enum



class AbstractGHService(SCMService):
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")

class GHServiceChecks(AbstractGHService):

    class CheckActionEnum(Enum):
        def __str__(self):
            return str(self.value)
        SCAN = "RERUNSCAN"
        CANCEL="CANCELSCAN"

    

    __max_content_chars = 65535
    __check_name = "CheckmarxOne Scan"
    __summary_text = "[CheckmarxOne](https://docs.checkmarx.com/) scans are orchestrated by [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow)"

    __pr_head_sha_query = parse("$.pull_request.head.sha")
    __check_req_action_pr_head_sha_query = parse("$.check_run.check_suite.pull_requests[0].head.sha")

    __run_response_query = parse("$.id")

    def __get_head_sha(self, pr_details : PRDetails) -> str:
        found = GHServiceChecks.__pr_head_sha_query.find(pr_details.event_context.message)

        if found is not None and len(found) == 0:
            found = GHServiceChecks.__check_req_action_pr_head_sha_query.find(pr_details.event_context.message)

        return found.pop().value

    async def __find_running_check(self, pr_details : PRDetails, status : str) -> Union[None, int]:
        head_sha = self.__get_head_sha(pr_details)

        id_query = parser.parse(f"$.check_runs[?(@.head_sha == \"{head_sha}\")].id")

        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/commits/{head_sha}/check-runs"
        query = {
            "check_name" : GHServiceChecks.__check_name,
            "status" : status
        }

        try:
            check_data = json_on_ok(await self.exec("GET", url, query = query,
                                  extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                  event_context=pr_details.event_context))
            
            found_check = id_query.find(check_data)
            if found_check:
                return found_check.pop().value
        except SCMAuthException as ex:
            GHServiceChecks.log().error("%s (The Github app may not have permission to read and write Checks)", ex)

    async def __update_run(self, pr_details : PRDetails, payload : Dict, run_id : int) -> None:
        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/check-runs/{run_id}"

        try:
            json_on_ok(await self.exec("PATCH", url, 
                                  extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                  body=json.dumps(payload), 
                                  event_context=pr_details.event_context))

        except SCMAuthException as ex:
            GHServiceChecks.log().error("%s (The Github app may not have permission to read and write Checks)", ex)

    async def __create_run(self, pr_details : PRDetails, payload : Dict) -> Union[int, None]:
        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/check-runs"

        try:
            create_data = json_on_ok(await self.exec("POST", url, 
                                  extra_headers={"accept" : "application/vnd.github+json", "Content-Type" : "application/json"}, 
                                  body=json.dumps(payload), 
                                  event_context=pr_details.event_context))

            return GHServiceChecks.__run_response_query.find(create_data).pop().value
        except SCMAuthException as ex:
            GHServiceChecks.log().error("%s (The Github app may not have permission to read and write Checks)", ex)

    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        
        # See if there is an existing run that is in status "queued"
        # this would mean it is a deferred scan.
        run_id = await self.__find_running_check(pr_details, "queued")

        payload = {
            "name" : GHServiceChecks.__check_name,
            "head_sha" : self.__get_head_sha(pr_details),
            "external_id" : scan_details.scanid, 
            "status" : "in_progress",
            "output" : {
                "title" : content.get_status_msg(GHServiceChecks.__max_content_chars),
                "summary" : GHServiceChecks.__summary_text,
                "text" : content.get_content(GHServiceChecks.__max_content_chars)
                },
            "actions" : [
                {
                    "label" : "Cancel scan",
                    "description" : "Cancels the running scan",
                    "identifier" : str(GHServiceChecks.CheckActionEnum.CANCEL)
                }
            ]
            
        }

        if run_id is None:
            # No pending scan, start a new scan in progress
            run_id = await self.__create_run(pr_details, payload)
        else:
            # Update the pending scan
            await self.__update_run(pr_details, payload, run_id)

        GHServiceChecks.log().debug("Check run ID %d updated for scan id %s", run_id, scan_details.scanid)


    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        # A pending scan should close other runs for the PR if they exist since the scan will start after
        # the pre-scan execution is complete.
        
        # No actions available for pending scans.
        payload = {
            "name" : GHServiceChecks.__check_name,
            "head_sha" : self.__get_head_sha(pr_details), 
            "status" : "queued",
            "output" : {
                "title" : content.get_status_msg(GHServiceChecks.__max_content_chars),
                "summary" : GHServiceChecks.__summary_text,
                "text" : content.get_content(GHServiceChecks.__max_content_chars)
                }
        }

        run_id = await self.__create_run(pr_details, payload)

        if run_id is not None:        
            GHServiceChecks.log().debug("Pending scan check run ID %d created for PR #%s", run_id, pr_details.pr_id)
        else:        
            GHServiceChecks.log().warning("No pending scan check created for PR #%s", pr_details.pr_id)


    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):

        run_id = await self.__find_running_check(pr_details, "in_progress")

        if run_id is None:
            GHServiceChecks.log().warning("No running check found in PR#%s for scan %s, no check updated.", pr_details.pr_id, scan_details.scanid)
        else:
            payload = {
                "name" : GHServiceChecks.__check_name,
                "head_sha" : self.__get_head_sha(pr_details),
                "external_id" : scan_details.scanid, 
                "status" : "completed",
                "conclusion" : "failure",
                "output" : {
                    "title" : content.get_status_msg(GHServiceChecks.__max_content_chars),
                    "summary" : GHServiceChecks.__summary_text,
                    "text" : content.get_content(GHServiceChecks.__max_content_chars)
                    },
                "actions" : [
                    {
                        "label" : "Re-run scan",
                        "description" : "Runs the scan again",
                        "identifier" : str(GHServiceChecks.CheckActionEnum.SCAN)
                    }]
            }

            await self.__update_run(pr_details, payload, run_id)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        # no actions are available after a successful scan

        run_id = await self.__find_running_check(pr_details, "in_progress")

        if run_id is None:
            GHServiceChecks.log().warning("No running check found in PR#%s for scan %s, no check updated.", pr_details.pr_id, scan_details.scanid)
        else:
            payload = {
                "name" : GHServiceChecks.__check_name,
                "head_sha" : self.__get_head_sha(pr_details),
                "external_id" : scan_details.scanid, 
                "status" : "completed",
                "conclusion" : "success",
                "output" : {
                    "title" : content.get_status_msg(GHServiceChecks.__max_content_chars),
                    "summary" : GHServiceChecks.__summary_text,
                    "text" : content.get_content(GHServiceChecks.__max_content_chars)
                    }
            }

            await self.__update_run(pr_details, payload, run_id)





class GHServiceCommitStatus(AbstractGHService):


    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_update_decorate")
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        raise NotImplementedError("exec_pr_scan_pending_decorate")

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_failure_decorate")

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_success_decorate")

class GHServiceBasic(AbstractGHService):
    __max_content_chars = 65535
    __api_page_max = 100


    def __comment_data_extractor(self, resp : Response):
        if resp.ok:
            json = resp.json()
            return json, len(json) >= GHServiceBasic.__api_page_max
        return None

    def __comment_list_args_gen(self, path : str, event_context : EventContext, offset : int):
        return { 
            "method" : "GET",
            "path" : path,
            "query" : {"per_page" : GHServiceBasic.__api_page_max, "page" : offset + 1},
            "event_context" : event_context
        }

    async def __create_or_update_pr_comment(self, organization : str, repo_slug : str, pr_number : str, content : str, 
        event_context : EventContext):

        content = { "body" : content}

        target_id = None

        async for comment in async_api_page_generator(self.exec, self.__comment_data_extractor,
            lambda offset: self.__comment_list_args_gen(f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", event_context, offset)):
            if 'id' in comment.keys() and 'body' in comment.keys():
                comment_id = comment['id']
                if PullRequestAbstractMarkdownComment.comment_matches_identifier(comment['body']):
                    target_id = comment_id
                    break

        if target_id is None:
            resp = json_on_ok(await self.exec("POST", f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", 
                                              body=json.dumps(content), event_context = event_context))
            action = "Created"
            target_id = resp['id']
        else:
            resp = json_on_ok(await self.exec("PATCH", f"/repos/{organization}/{repo_slug}/issues/comments/{target_id}", 
                                              body=json.dumps(content), event_context = event_context))
            action = "Updated"
        
        GHServiceBasic.log().debug(f"{action} comment {target_id} in PR {pr_number}")


    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        await self.__create_or_update_pr_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, 
                                                 content.get_content(self.__max_content_chars), pr_details.event_context)
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, 
                                                 content.get_content(self.__max_content_chars), pr_details.event_context)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        return await self.exec_pr_scan_update_decorate(pr_details, content, scan_details)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        return await self.exec_pr_scan_update_decorate(pr_details, content, scan_details)
    




