import asyncio, aio_pika, logging, pamqp.commands
from cxoneflow_logging import SecretRegistry
from ssl import create_default_context, CERT_NONE
import urllib.parse
from datetime import timedelta
from cxone_service import CxOneService
from cxone_service import CxOneService
from cxone_api.scanning import ScanLoader, ScanInspector
from scm_services import SCMService
from .messaging import ScanAwaitMessage, ScanAnnotationMessage, ScanFeedbackMessage, PRDetails
from .workflow_base import AbstractWorkflow
from . import ScanStates, ScanWorkflow, FeedbackWorkflow
from cxone_api.exceptions import ResponseException
from .pr import PullRequestAnnotation
import markdown as md


class WorkflowStateService:


    EXCHANGE_SCAN_INPUT = "Scan In"
    EXCHANGE_SCAN_WAIT = "Scan Await"
    EXCHANGE_SCAN_ANNOTATE = "Scan Annotate"
    EXCHANGE_SCAN_FEEDBACK = "Scan Feedback"
    EXCHANGE_SCAN_POLLING = "Scan Polling Delivery"

    QUEUE_SCAN_POLLING = "Polling Scans"
    QUEUE_SCAN_WAIT = "Awaited Scans"
    QUEUE_SCAN_PR_ANNOTATE = "PR Annotating"
    QUEUE_FEEDBACK_PR = "PR Feedback"

    ROUTEKEY_POLL_BINDING = F"{ScanStates.AWAIT}.*.*"
    ROUTEKEY_FEEDBACK_PR = f"{ScanStates.FEEDBACK}.{FeedbackWorkflow.PR}.*"
    ROUTEKEY_ANNOTATE_PR = f"{ScanStates.ANNOTATE}.{FeedbackWorkflow.PR}.*"
    
    @staticmethod
    def log():
        return logging.getLogger("WorkflowStateService")

    def __init__(self, moniker, amqp_url , amqp_user, amqp_password, ssl_verify, pr_workflow : AbstractWorkflow, max_interval_seconds : timedelta = 600, 
                 backoff_scalar : int = 2):
        self.__lock = asyncio.Lock()
        self.__max_interval = timedelta(seconds=max_interval_seconds)
        self.__backoff = backoff_scalar
        self.__amqp_url = amqp_url
        self.__amqp_user = amqp_user
        self.__amqp_password = amqp_password
        self.__ssl_verify = ssl_verify
        self.__client = None
        self.__service_moniker = moniker

        self.__workflow_map = {
            ScanWorkflow.PR : pr_workflow
        }

        netloc = urllib.parse.urlparse(self.__amqp_url).netloc

        if '@' in netloc:
            SecretRegistry.register(netloc.split("@")[0])

    
    @property
    def use_ssl(self):
        return urllib.parse.urlparse(self.__amqp_url).scheme == "amqps"
    
    async def execute_poll_scan_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService):

        requeue_on_finally = True

        swm = ScanAwaitMessage.from_binary(msg.body)

        if swm.is_expired():
            WorkflowStateService.log().warn(f"Scan id {swm.scanid} polling timeout expired at {swm.drop_by}. Polling for this scan has been stopped.")
            await msg.ack()
        else:
            async with await (await self.mq_client()).channel() as write_channel:
                try:
                    inspector = await cxone_service.load_scan_inspector(swm.scanid)

                    try:

                        if not inspector.executing:
                            
                            requeue_on_finally = False
                            
                            if inspector.successful:
                                WorkflowStateService.log().info(f"Scan success for scan id {swm.scanid}, enqueuing feedback workflow.")
                                await self.__workflow_map[swm.workflow].feedback_start(await self.mq_client(), swm.moniker, swm.scanid, **(swm.workflow_details))
                            else:
                                WorkflowStateService.log().info(f"Scan failure for scan id {swm.scanid}, enqueuing annotation workflow.")
                                await self.__workflow_map[swm.workflow].annotation_start(await self.mq_client(), swm.moniker, swm.scanid, 
                                                                                         inspector.state_msg, **(swm.workflow_details))
                    except BaseException as bex:
                        WorkflowStateService.log().exception(bex)
                    finally:
                            await msg.ack()

                except ResponseException as ex:
                    WorkflowStateService.log().exception(ex)
                    WorkflowStateService.log().error(f"Polling for scan id {swm.scanid} stopped due to exception.")
                    requeue_on_finally = False
                    await msg.ack()
                finally:
                    if requeue_on_finally:
                        exchange = await write_channel.get_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT)

                        if exchange:
                            orig_exp = int(msg.headers['x-death'][0]['original-expiration'])
                            backoff=min(timedelta(milliseconds=orig_exp * self.__backoff), self.__max_interval)
                            new_msg = aio_pika.Message(swm.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                        expiration=backoff)

                            result = await exchange.publish(new_msg, routing_key=msg.routing_key)

                            if type(result) == pamqp.commands.Basic.Ack:
                                WorkflowStateService.log().debug(f"Scan id {swm.scanid} poll message re-enqueued with delay {backoff.total_seconds()}s.")
                                await msg.ack()
                            else:
                                WorkflowStateService.log().debug(f"Scan id {swm.scanid} failed to re-enqueue new poll message.")
                                await msg.nack()



    async def mq_client(self) -> aio_pika.abc.AbstractRobustConnection:
        async with self.__lock:

            if self.__client is None:
                WorkflowStateService.log().debug(f"Creating AMQP connection to: {self.__amqp_url}")
                ctx = None

                if self.use_ssl and not self.__ssl_verify:
                    ctx = create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = CERT_NONE

                self.__client = await aio_pika.connect_robust(self.__amqp_url, \
                                                    login=self.__amqp_user if self.__amqp_user is not None else "guest", \
                                                    password=self.__amqp_password if self.__amqp_password is not None else "guest", \
                                                    ssl_context=ctx)
        return self.__client


    async def execute_pr_annotate_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService, scm_service : SCMService):
        am = ScanAnnotationMessage.from_binary(msg.body)
        pr_details = PRDetails.from_dict(am.workflow_details)

        if await self.__workflow_map[ScanWorkflow.PR].is_enabled():
            inspector = await cxone_service.load_scan_inspector(am.scanid)

            if inspector is not None:
                annotation = PullRequestAnnotation(cxone_service.display_link, inspector.project_id, am.scanid, am.annotation)
                await scm_service.exec_pr_annotate(pr_details.organization, pr_details.repo_project, pr_details.repo_slug, pr_details.pr_id,
                                                am.scanid, md.markdown(annotation.content))
                await msg.ack()
            else:
                WorkflowStateService.log().error(f"Unable for load scan {am.scanid}")
                await msg.nack()
        else:
            await msg.ack()



    async def start_pr_scan_workflow(self, scanid : str, details : PRDetails) -> None:
        await self.__workflow_map[ScanWorkflow.PR].workflow_start(await self.mq_client(), self.__service_moniker, scanid, **(details.as_dict()))
        await self.start_pr_annotation(scanid, "Scan started", details)

    async def start_pr_feedback(self, scanid : str, details : PRDetails):
        await self.__workflow_map[ScanWorkflow.PR].feedback_start(await self.mq_client(), self.__service_moniker, scanid, **(details.as_dict()))

    async def start_pr_annotation(self, scanid : str, annotation : str, details : PRDetails):
        await self.__workflow_map[ScanWorkflow.PR].annotation_start(await self.mq_client(), self.__service_moniker, scanid, annotation, **(details.as_dict()))
