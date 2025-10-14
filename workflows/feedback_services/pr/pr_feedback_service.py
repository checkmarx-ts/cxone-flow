from cxone_service import CxOneService, CxOneException
from scm_services.scm import SCMService
from workflows.messaging import ScanAnnotationMessage, ScanFeedbackMessage, PRDetails, ScanAwaitMessage
from workflows.enums import ScanWorkflow
from workflows.exceptions import WorkflowException
from workflows.pr import PullRequestMarkdownAnnotation, PullRequestMarkdownFeedback
from workflows.feedback_services.pr.abstract_pr_service import AbstractPRFeedbackService

class PRThreadFeedbackService(AbstractPRFeedbackService):

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
            PRThreadFeedbackService.log().error("Unrecoverable exception, aborting PR annotation for scan id %s.", msg.scanid)
            PRThreadFeedbackService.log().exception(bex)
        
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
            PRThreadFeedbackService.log().exception(ex)
        except BaseException as bex:
            PRThreadFeedbackService.log().error("Unrecoverable exception, aborting PR feedback.")
            PRThreadFeedbackService.log().exception(bex)
            
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
