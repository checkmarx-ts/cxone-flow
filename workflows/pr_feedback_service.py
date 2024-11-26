import aio_pika, logging, pamqp.commands
from datetime import timedelta
from cxone_service import CxOneService
from cxone_service import CxOneService
from scm_services import SCMService
from .messaging import ScanAwaitMessage, ScanAnnotationMessage, ScanFeedbackMessage, PRDetails
from .feedback_workflow_base import AbstractFeedbackWorkflow
from . import ScanStates, ScanWorkflow, FeedbackWorkflow
from cxone_api.exceptions import ResponseException
from .pr import PullRequestAnnotation, PullRequestFeedback
from .base_service import BaseWorkflowService
from cxone_service import CxOneException

class PRFeedbackService(BaseWorkflowService):
    EXCHANGE_SCAN_INPUT = "Scan In"
    EXCHANGE_SCAN_WAIT = "Scan Await"
    EXCHANGE_SCAN_ANNOTATE = "Scan Annotate"
    EXCHANGE_SCAN_FEEDBACK = "Scan Feedback"
    EXCHANGE_SCAN_POLLING = "Scan Polling Delivery"

    QUEUE_SCAN_POLLING = "Polling Scans"
    QUEUE_SCAN_WAIT = "Awaited Scans"
    QUEUE_ANNOTATE_PR = "PR Annotating"
    QUEUE_FEEDBACK_PR = "PR Feedback"
    
    ROUTEKEY_POLL_BINDING = F"{ScanStates.AWAIT}.*.*"
    ROUTEKEY_FEEDBACK_PR = f"{ScanStates.FEEDBACK}.{FeedbackWorkflow.PR}.*"
    ROUTEKEY_ANNOTATE_PR = f"{ScanStates.ANNOTATE}.{FeedbackWorkflow.PR}.*"

    
    @staticmethod
    def log():
        return logging.getLogger("PRFeedbackService")

    def __init__(self, moniker : str, amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool, server_base_url : str, pr_workflow : AbstractFeedbackWorkflow, 
                 max_interval_seconds : timedelta = 600, backoff_scalar : int = 2):
        
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__max_interval = timedelta(seconds=max_interval_seconds)
        self.__backoff = backoff_scalar
        self.__service_moniker = moniker
        self.__server_base_url = server_base_url

        self.__workflow_map = {
            ScanWorkflow.PR : pr_workflow
        }
   
    
    async def execute_poll_scan_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService):

        requeue_on_finally = True

        swm = ScanAwaitMessage.from_binary(msg.body)

        if swm.is_expired():
            PRFeedbackService.log().warning(f"Scan id {swm.scanid} polling timeout expired at {swm.drop_by}. Polling for this scan has been stopped.")
            await msg.ack()
        else:
            async with await (await self.mq_client()).channel() as write_channel:
                try:
                    inspector = await cxone_service.load_scan_inspector(swm.scanid)

                    if not inspector.executing:
                        try:
                            requeue_on_finally = False
                            
                            if inspector.successful:
                                PRFeedbackService.log().info(f"Scan success for scan id {swm.scanid}, enqueuing feedback workflow.")
                                await self.__workflow_map[swm.workflow].feedback_start(await self.mq_client(), swm.moniker, swm.projectid, swm.scanid, **(swm.workflow_details))
                            else:
                                PRFeedbackService.log().info(f"Scan failure for scan id {swm.scanid}, enqueuing annotation workflow.")
                                await self.__workflow_map[swm.workflow].annotation_start(await self.mq_client(), swm.moniker, swm.projectid, swm.scanid, 
                                                                                        inspector.state_msg, **(swm.workflow_details))
                        except BaseException as bex:
                            PRFeedbackService.log().exception(bex)
                        finally:
                                await msg.ack()

                except ResponseException as ex:
                    PRFeedbackService.log().exception(ex)
                    PRFeedbackService.log().error(f"Polling for scan id {swm.scanid} stopped due to exception.")
                    requeue_on_finally = False
                    await msg.ack()
                finally:
                    if requeue_on_finally:
                        exchange = await write_channel.get_exchange(PRFeedbackService.EXCHANGE_SCAN_INPUT)

                        if exchange:
                            orig_exp = int(msg.headers['x-death'][0]['original-expiration'])
                            backoff=min(timedelta(milliseconds=orig_exp * self.__backoff), self.__max_interval)
                            new_msg = aio_pika.Message(swm.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                        expiration=backoff)

                            result = await exchange.publish(new_msg, routing_key=msg.routing_key)

                            if type(result) == pamqp.commands.Basic.Ack:
                                PRFeedbackService.log().debug(f"Scan id {swm.scanid} poll message re-enqueued with delay {backoff.total_seconds()}s.")
                                await msg.ack()
                            else:
                                PRFeedbackService.log().debug(f"Scan id {swm.scanid} failed to re-enqueue new poll message.")
                                await msg.nack()


    async def execute_pr_annotate_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService, scm_service : SCMService):
        am = ScanAnnotationMessage.from_binary(msg.body)
        pr_details = PRDetails.from_dict(am.workflow_details)

        try:
            if await self.__workflow_map[ScanWorkflow.PR].is_enabled():
                inspector = await cxone_service.load_scan_inspector(am.scanid)

                if inspector is not None:
                    annotation = PullRequestAnnotation(cxone_service.display_link, inspector.project_id, am.scanid, am.annotation, pr_details.source_branch,
                                                       self.__server_base_url)
                    await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                    am.scanid, annotation.full_content, annotation.summary_content, pr_details.event_context)
                    await msg.ack()
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
        am = ScanFeedbackMessage.from_binary(msg.body)
        pr_details = PRDetails.from_dict(am.workflow_details)
        try:
            if await self.__workflow_map[ScanWorkflow.PR].is_enabled():
                report = await cxone_service.retrieve_report(am.projectid, am.scanid)
                if report is None:
                    await msg.nack()
                else:
                    feedback = PullRequestFeedback(self.__workflow_map[ScanWorkflow.PR].excluded_severities, 
                        self.__workflow_map[ScanWorkflow.PR].excluded_states, cxone_service.display_link, am.projectid, am.scanid, report, 
                        scm_service.create_code_permalink, pr_details, self.__server_base_url)
                    await scm_service.exec_pr_decorate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                    am.scanid, feedback.full_content, feedback.summary_content, pr_details.event_context)
                    await msg.ack()
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
        await self.__workflow_map[ScanWorkflow.PR].workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))
        await self.start_pr_annotation(projectid, scanid, "Scan started", details)

    async def start_pr_feedback(self, projectid : str, scanid : str, details : PRDetails):
        await self.__workflow_map[ScanWorkflow.PR].feedback_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))

    async def start_pr_annotation(self, projectid : str, scanid : str, annotation : str, details : PRDetails):
        await self.__workflow_map[ScanWorkflow.PR].annotation_start(await self.mq_client(), self.__service_moniker, projectid, scanid, annotation, **(details.as_dict()))

