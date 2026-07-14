from scm_services.scm import SCMService
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage

class BBCService(SCMService):

  async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
      raise NotImplementedError("exec_pr_scan_update_decorate")
  
  async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
      raise NotImplementedError("exec_pr_scan_pending_decorate")

  async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
      raise NotImplementedError("exec_pr_scan_failure_decorate")

  async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
      raise NotImplementedError("exec_pr_scan_success_decorate")

  async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
      raise NotImplementedError("exec_pr_unrecoverable_error")

  async def exec_pr_prescan_failure(self, pr_details : PRDetails, fail_msg : str):
      raise NotImplementedError("exec_pr_prescan_failure")

  def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
      raise NotImplementedError("create_code_permalink")
