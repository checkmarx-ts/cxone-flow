from workflows import AbstractPRFeedbackWorkflow, CxOneFlowAbstractWorkflowService
from workflows.feedback_services.pr.queue_constants import PRQueueConstants
from workflows.enums import ScanStates, FeedbackWorkflow
from workflows.messaging import PRDetails, ScanAnnotationMessage, ScanFeedbackMessage, PreScanAnnotationMessage
from cxone_service import CxOneService
from scm_services.scm import SCMService

class AbstractPRFeedbackService(CxOneFlowAbstractWorkflowService):

    def __init__(self, moniker : str, server_base_url : str, pr_workflow : AbstractPRFeedbackWorkflow, 
                 amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__server_base_url = server_base_url
        self.__workflow = pr_workflow

    @property
    def moniker(self) -> str:
        return self.__service_moniker
    
    @property
    def server_base_url(self) -> str:
        return self.__server_base_url
    
    @property
    def workflow(self) -> AbstractPRFeedbackWorkflow:
        return self.__workflow

    @staticmethod
    def make_topic(state : ScanStates, workflow : FeedbackWorkflow, moniker : str):
        return f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PRQueueConstants.PR_TOPIC_PREFIX}{state}.{workflow}.{moniker}"
    
    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails, cxone_service : CxOneService, scm_service : SCMService) -> None:
        raise NotImplementedError("start_pr_scan_workflow")

    async def start_delegated_pr_scan_workflow(self, details : PRDetails, cxone_service : CxOneService, scm_service : SCMService) -> None:
        raise NotImplementedError("start_delegated_pr_scan_workflow")
    
    async def process_pr_notice(self, msg : ScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_notice")

    async def process_prescan_pr_notice(self, msg : PreScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_prescan_pr_notice")
    
    async def process_pr_feedback(self, msg : ScanFeedbackMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_feedback")
