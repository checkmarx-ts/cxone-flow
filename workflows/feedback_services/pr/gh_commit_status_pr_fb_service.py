from workflows.feedback_services.pr.pr_feedback_service import PRFeedbackService
from workflows.messaging import ScanAnnotationMessage, ScanFeedbackMessage, PRDetails, ScanAwaitMessage
from cxone_service import CxOneService
from scm_services.scm import SCMService

class GithubCommitStatusPRFBService(PRFeedbackService):
    
    def __init__(self, wait_for_scan : bool, ignore_break_build : bool, **kwargs):
        super().__init__(**kwargs)

    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails, cxone_service : CxOneService, scm_service : SCMService) -> None:
        # TODO: Block PR with pending status "waiting for scan to start"
        return super().start_pr_scan_workflow(projectid, scanid, details, cxone_service, scm_service)
    
    async def process_pr_notice(self, msg : ScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_notice")
    
    async def process_pr_feedback(self, msg : ScanFeedbackMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_feedback")


    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        raise NotImplementedError("handle_awaited_scan")
    
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        raise NotImplementedError("handle_awaited_scan_error")    
