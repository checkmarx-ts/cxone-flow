import aio_pika, logging
from cxone_service import CxOneService
from scm_services import SCMService
from workflows.messaging import ScanAnnotationMessage, ScanFeedbackMessage, PRDetails, ScanAwaitMessage
from workflows.feedback_workflow_base import AbstractPRFeedbackWorkflow
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.pr import PullRequestAnnotation, PullRequestFeedback
from workflows.base_service import CxOneFlowAbstractWorkflowService
from cxone_service import CxOneException

class PRFeedbackService(CxOneFlowAbstractWorkflowService):
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
    
    @staticmethod
    def log():
        return logging.getLogger("PRFeedbackService")
    

    def __init__(self, moniker : str, server_base_url : str, pr_workflow : AbstractPRFeedbackWorkflow, 
                 amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__server_base_url = server_base_url
        self.__workflow = pr_workflow


    async def execute_pr_annotate_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService, scm_service : SCMService):
        am = await self._safe_deserialize_body(msg, ScanAnnotationMessage)
        pr_details = PRDetails.from_dict(am.workflow_details)

        try:
            if await self.__workflow.is_enabled():
                inspector = await cxone_service.load_scan_inspector(am.scanid)

                if inspector is not None:
                    annotation = PullRequestAnnotation(cxone_service.display_link, inspector.project_id, am.scanid, am.annotation, pr_details.source_branch,
                                                       self.__server_base_url)
                    await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                    am.scanid, annotation.full_content, annotation.summary_content, pr_details.event_context)
                    await msg.ack()

                    self.log().info(f"{am.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Annotation complete")
                else:
                    PRFeedbackService.log().error(f"Unable for load scan {am.scanid}")
                    await msg.nack()
            else:
                await msg.ack()
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR annotation.")
            PRFeedbackService.log().exception(bex)
            await msg.ack()


    async def execute_pr_feedback_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService, scm_service : SCMService):
        fm = await self._safe_deserialize_body(msg, ScanFeedbackMessage)
        pr_details = PRDetails.from_dict(fm.workflow_details)
        
        try:
            if await self.__workflow.is_enabled():
                report = await cxone_service.retrieve_report(fm.projectid, fm.scanid)
                if report is None:
                    await msg.nack()
                else:
                    feedback = PullRequestFeedback(self.__workflow.excluded_severities, 
                        self.__workflow.excluded_states, cxone_service.display_link, fm.projectid, fm.scanid, report, 
                        scm_service.create_code_permalink, pr_details, self.__server_base_url)
                    await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                    fm.scanid, feedback.full_content, feedback.summary_content, pr_details.event_context)
                    await msg.ack()

                    self.log().info(f"{fm.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Feedback complete")
            else:
                await msg.ack()
        except CxOneException as ex:
            PRFeedbackService.log().exception(ex)
            await msg.nack()
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR feedback.")
            PRFeedbackService.log().exception(bex)
            await msg.ack()


    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails) -> None:
        await self.__workflow.workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))
        await self.__workflow.annotation_start(await self.mq_client(), self.__service_moniker, projectid, scanid, "Scan Started", **(details.as_dict()))

    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.__workflow.feedback_start(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, **(msg.workflow_details))
    
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.__workflow.feedback_error(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, error_msg, **(msg.workflow_details))
