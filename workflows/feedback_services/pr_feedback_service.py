from cxone_service import CxOneService
from scm_services import SCMService
from workflows.messaging import ScanAnnotationMessage, ScanFeedbackMessage, PRDetails, ScanAwaitMessage
from workflows.feedback_workflow_base import AbstractPRFeedbackWorkflow
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.exceptions import WorkflowException
from workflows.pr import PullRequestMarkdownAnnotation, PullRequestMarkdownFeedback
from workflows.base_service import CxOneFlowAbstractWorkflowService
from cxone_service import CxOneException


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

    PR_ELEMENT_PREFIX = "pr:"
    PR_TOPIC_PREFIX = "pr."

    EXCHANGE_SCAN_INPUT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan In"
    EXCHANGE_SCAN_WAIT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Await"
    EXCHANGE_SCAN_POLLING_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Polling Delivery"


    EXCHANGE_SCAN_ANNOTATE = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Annotate"
    EXCHANGE_SCAN_FEEDBACK = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Feedback"

    QUEUE_SCAN_POLLING_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Polling Scans"
    QUEUE_SCAN_WAIT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Awaited Scans"


    QUEUE_ANNOTATE_PR = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}PR Annotating"
    QUEUE_FEEDBACK_PR = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}PR Feedback"
    
    ROUTEKEY_POLL_BINDING_LEGACY = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.AWAIT}.*.*"


    ROUTEKEY_FEEDBACK_PR = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PR}.*"
    ROUTEKEY_ANNOTATE_PR = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.ANNOTATE}.{FeedbackWorkflow.PR}.*"

    @staticmethod
    def make_topic(state : ScanStates, workflow : FeedbackWorkflow, moniker : str):
        return f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PRFeedbackService.PR_TOPIC_PREFIX}{state}.{workflow}.{moniker}"
    
    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails) -> None:
        raise NotImplementedError("start_pr_scan_workflow")
    
    async def process_pr_notice(self, msg : ScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_notice")
    
    async def process_pr_feedback(self, msg : ScanFeedbackMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        raise NotImplementedError("process_pr_feedback")


class PRFeedbackService(AbstractPRFeedbackService):

    async def process_pr_notice(self, msg : ScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> None:
        pr_details = PRDetails.from_dict(msg.workflow_details)

        try:
            if await self.workflow.is_enabled():
                annotation = PullRequestMarkdownAnnotation(cxone_service.display_link, msg.projectid, msg.scanid, msg.annotation, pr_details.source_branch,
                                                    self.server_base_url)
                await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                msg.scanid, annotation.full_content, annotation.summary_content, pr_details.event_context)
                self.log().info(f"{msg.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Annotation complete")

            return True
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR annotation for scan id %s.", msg.scanid)
            PRFeedbackService.log().exception(bex)
        
        return False
    
    async def process_pr_feedback(self, msg : ScanFeedbackMessage, cxone_service : CxOneService, scm_service : SCMService) -> None:
        pr_details = PRDetails.from_dict(msg.workflow_details)

        try:
            if await self.workflow.is_enabled():
                report = await cxone_service.retrieve_report(msg.projectid, msg.scanid)
                if report is None:
                    raise WorkflowException.missing_report(msg.projectid, msg.scanid)
                else:
                    feedback = PullRequestMarkdownFeedback(self.workflow.excluded_severities, 
                        self.workflow.excluded_states, cxone_service.display_link, msg.projectid, msg.scanid, report, 
                        scm_service.create_code_permalink, pr_details, self.server_base_url)
                    await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                    msg.scanid, feedback.full_content, feedback.summary_content, pr_details.event_context)
                    self.log().info(f"{msg.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Feedback complete")
            return True
        except CxOneException as ex:
            PRFeedbackService.log().exception(ex)
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR feedback.")
            PRFeedbackService.log().exception(bex)
            
        return False
        


    # From AbstractPRFeedbackService
    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails) -> None:
        await self.workflow.workflow_start(await self.mq_client(), self.moniker, projectid, scanid, **(details.as_dict()))
        await self.workflow.annotation_start(await self.mq_client(), self.moniker, projectid, scanid, "Scan Started", **(details.as_dict()))


    # From CxOneFlowAbstractWorkflowService
    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.workflow.feedback_start(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, **(msg.workflow_details))
    
    # From CxOneFlowAbstractWorkflowService
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.workflow.feedback_error(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, error_msg, **(msg.workflow_details))
