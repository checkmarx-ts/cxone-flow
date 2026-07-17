import json
from .bbc import BBCServiceBasic
from scm_services.policy import PolicyProperties
from workflows.messaging import PRDetails, ScanMessage
from workflows.pr_content import PullRequestAbstractMarkdownComment
from workflows.pr_content import PullRequestCommentContent

class BBCServiceChecks(BBCServiceBasic, PolicyProperties):

    __check_key = "cxoneflow"
    __max_description_length = 128

    def __init__(self, check_name : str, **kwargs):
        BBCServiceBasic.__init__(self, **kwargs)
        PolicyProperties.__init__(self, check_name)

    async def __update_check(self, state: str, pr_details : PRDetails, description: str, url : str):
      payload = {
          "key": BBCServiceChecks.__check_key,
          "state": state,
          "description": description,
          "url": url,
          "name": self.check_name,
      }

      await self.exec("POST", f"/repositories/{pr_details.organization}/{pr_details.repo_slug}/commit/{pr_details.source_hash}/statuses/build",
                      body=json.dumps(payload), extra_headers={"Content-Type" : "application/json"})
      
    @property
    def services(self):
      from config.server import CxOneFlowConfig
      return CxOneFlowConfig.retrieve_services_by_moniker(self.moniker)


    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):

      await self.__update_check("INPROGRESS",
                                pr_details,
                                content.get_status_msg(BBCServiceChecks.__max_description_length),
                                content.scan_url)
      
      await BBCServiceBasic.exec_pr_scan_update_decorate(self, pr_details, content, scan_details)

    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):

      await self.__update_check("INPROGRESS",
                                pr_details,
                                content.get_status_msg(BBCServiceChecks.__max_description_length),
                                self.services.cxone.display_link)

      await BBCServiceBasic.exec_pr_scan_pending_decorate(self, pr_details, content)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
      await self.__update_check("FAILED",
                                pr_details,
                                content.get_status_msg(BBCServiceChecks.__max_description_length),
                                content.scan_url)

      await BBCServiceBasic.exec_pr_scan_failure_decorate(self, pr_details, content, scan_details)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):

      await self.__update_check("SUCCESSFUL",
                                pr_details,
                                content.get_status_msg(BBCServiceChecks.__max_description_length),
                                content.scan_url)

      await BBCServiceBasic.exec_pr_scan_success_decorate(self, pr_details, content, scan_details)


    async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
      await self.__update_check("FAILED",
                                pr_details,
                                fail_msg,
                                PullRequestAbstractMarkdownComment.make_cxone_scan_url(self.services.cxone.display_link,
                                                                                        scan_details.projectid, 
                                                                                        scan_details.scanid,
                                                                                        pr_details.target_branch))

      await BBCServiceBasic.exec_pr_unrecoverable_error(self, pr_details, scan_details, fail_msg)

    async def exec_pr_prescan_failure(self, pr_details : PRDetails, fail_msg : str):
      await self.__update_check("FAILED",
                                pr_details,
                                fail_msg,
                                self.services.cxone.display_link)
      await BBCServiceBasic.exec_pr_prescan_failure(self, pr_details, fail_msg)

