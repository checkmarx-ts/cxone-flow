from scm_services.gh.abstract import AbstractGHService
from scm_services.policy import PolicyProperties
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
from cxone_api.util import json_on_ok
from api_utils.apisession import SCMAuthException
from enum import Enum
from typing import Union, Dict
from jsonpath_ng.ext import parser
from jsonpath_ng import parse
import json

class GHServiceChecks(AbstractGHService, PolicyProperties):

    class CheckActionEnum(Enum):
        def __str__(self):
            return str(self.value)
        SCAN = "RERUNSCAN"
        CANCEL="CANCELSCAN"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    __max_content_chars = 65535
    __summary_text = "[CheckmarxOne](https://docs.checkmarx.com/) scans are orchestrated by [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow)"

    __check_req_action_pr_head_sha_query = parse("$.check_run.check_suite.pull_requests[0].head.sha")

    __run_response_query = parse("$.id")

    def _get_head_sha(self, pr_details : PRDetails) -> Union[str, None]:
        found = GHServiceChecks.__check_req_action_pr_head_sha_query.find(pr_details.event_context.message)

        if found is not None and len(found) > 0:
            return found.pop().value
        else:
            return AbstractGHService._get_head_sha(self, pr_details)
        

    async def __find_running_check(self, pr_details : PRDetails, status : str) -> Union[None, int]:
        head_sha = self._get_head_sha(pr_details)

        if head_sha is None:
            return None

        id_query = parser.parse(f"$.check_runs[?(@.head_sha == \"{head_sha}\")].id")

        url = f"/repos/{pr_details.organization}/{pr_details.repo_slug}/commits/{head_sha}/check-runs"
        query = {
            "check_name" : self.check_name,
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
            "name" : self.check_name,
            "head_sha" : self._get_head_sha(pr_details),
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
            "name" : self.check_name,
            "head_sha" : self._get_head_sha(pr_details), 
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
                "name" : self.check_name,
                "head_sha" : self._get_head_sha(pr_details),
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
                "name" : self.check_name,
                "head_sha" : self._get_head_sha(pr_details),
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

    async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
        run_id = await self.__find_running_check(pr_details, "in_progress")

        if run_id is None:
            GHServiceChecks.log().warning("No running check found in PR#%s for scan %s, no check updated.", pr_details.pr_id, scan_details.scanid)
        else:
            payload = {
                "name" : self.check_name,
                "head_sha" : self._get_head_sha(pr_details),
                "external_id" : scan_details.scanid, 
                "status" : "completed",
                "conclusion" : "failure",
                "output" : {
                    "title" : "Unrecoverable Error",
                    "summary" : GHServiceChecks.__summary_text,
                    "text" : fail_msg
                    },
                "actions" : [
                    {
                        "label" : "Re-run scan",
                        "description" : "Runs the scan again",
                        "identifier" : str(GHServiceChecks.CheckActionEnum.SCAN)
                    }]
            }

            await self.__update_run(pr_details, payload, run_id)

    async def exec_pr_prescan_failure(self, pr_details : PRDetails, fail_msg : str):
        run_id = await self.__find_running_check(pr_details, "queued")

        if run_id is None:
            GHServiceChecks.log().warning("No queued prescan check found in PR#%s, no check updated.", pr_details.pr_id)
        else:
            payload = {
                "name" : self.check_name,
                "head_sha" : self._get_head_sha(pr_details),
                "status" : "completed",
                "conclusion" : "failure",
                "output" : {
                    "title" : "Prescan failure",
                    "summary" : GHServiceChecks.__summary_text,
                    "text" : fail_msg
                    }
            }

            await self.__update_run(pr_details, payload, run_id)
