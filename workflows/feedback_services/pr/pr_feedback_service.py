from cxone_service import CxOneService, CxOneException
from scm_services.scm import SCMService
from workflows.messaging import (ScanAnnotationMessage, 
                                 ScanFeedbackMessage, 
                                 PRDetails, 
                                 ScanAwaitMessage, 
                                 PreScanAnnotationMessage)
from workflows.enums import ScanWorkflow
from workflows.exceptions import WorkflowException
from workflows.pr_content import (PullRequestMarkdownAnnotation, 
                                  PullRequestMarkdownFeedback, 
                                  PrescanPullRequestMarkdownAnnotation)
from workflows.feedback_services.pr.abstract_pr_service import AbstractPRFeedbackService

class PRFeedbackService(AbstractPRFeedbackService):

    async def process_prescan_pr_notice(self, msg : PreScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> bool:
        pr_details = PRDetails.from_dict(msg.workflow_details)
        try:
            if await self.workflow.is_enabled():
                await scm_service.exec_pr_scan_pending_decorate(pr_details, PrescanPullRequestMarkdownAnnotation(msg.annotation))
                self.log().info(f"{msg.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Prescan annotation complete")

            return True
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR prescan annotation for PR id %s@%s.", pr_details.pr_id, pr_details.clone_url)
            PRFeedbackService.log().exception(bex)
        
        return False

    async def process_pr_notice(self, msg : ScanAnnotationMessage, cxone_service : CxOneService, scm_service : SCMService) -> None:
        pr_details = PRDetails.from_dict(msg.workflow_details)
        try:
            if await self.workflow.is_enabled():
                annotation = PullRequestMarkdownAnnotation(cxone_service.display_link, msg.projectid, msg.scanid, msg.annotation, pr_details.source_branch, self.server_base_url)
                await scm_service.exec_pr_scan_update_decorate(pr_details, annotation, msg)
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
                    status_msg = f"Scan {msg.scanid}: " + (msg.error_msg if msg.is_error else "completed")

                    feedback = PullRequestMarkdownFeedback(self.workflow.excluded_severities, 
                        self.workflow.excluded_states, cxone_service.display_link, msg.projectid, msg.scanid, report, 
                        scm_service.create_code_permalink, pr_details, 
                        await (cxone_service.get_policy_violation_inspector(msg.projectid, msg.scanid)).policy_violations, 
                        self.server_base_url, status_msg)
                    
                    if not msg.is_error:
                        await scm_service.exec_pr_scan_success_decorate(pr_details, feedback, msg)
                    else:
                        await scm_service.exec_pr_scan_failure_decorate(pr_details, feedback, msg)

                    self.log().info(f"{msg.moniker}: PR {pr_details.pr_id}@{pr_details.clone_url}: Feedback complete")

            return True
        except CxOneException as ex:
            PRFeedbackService.log().exception(ex)
            await scm_service.exec_pr_unrecoverable_error(pr_details, msg, "CxOneFlow: " + str(ex))
        except BaseException as bex:
            PRFeedbackService.log().error("Unrecoverable exception, aborting PR feedback.")
            PRFeedbackService.log().exception(bex)
            await scm_service.exec_pr_unrecoverable_error(pr_details, msg, "CxOneFlow: " + str(bex))
            
        return False


    async def start_pr_scan_workflow(self, projectid : str, scanid : str, details : PRDetails, cxone_service : CxOneService, scm_service : SCMService) -> None:
        await self.workflow.workflow_start(await self.mq_client(), self.moniker, projectid, scanid, **(details.as_dict()))
        await self.workflow.annotation_start(await self.mq_client(), self.moniker, projectid, scanid, "CheckmarxOne scan started", **(details.as_dict()))

    async def start_delegated_pr_scan_workflow(self, details : PRDetails, cxone_service : CxOneService, scm_service : SCMService) -> None:
        await self.workflow.prescan_annotation_start(await self.mq_client(), self.moniker, "CheckmarxOne pre-scan is now processing, please wait.", **(details.as_dict()))

    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.workflow.feedback_start(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, **(msg.workflow_details))
    
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        if msg.workflow == ScanWorkflow.PR:
            await self.workflow.feedback_error(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, error_msg, **(msg.workflow_details))
