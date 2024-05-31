import asyncio, aio_pika, logging
from cxoneflow_logging import SecretRegistry
from ssl import create_default_context, CERT_NONE
from enum import Enum
import urllib.parse
from .workflow_base import WorkflowBase


class WorkflowStateService:

    class __base_enum(Enum):
        def __str__(self):
            return str(self.value)   

        def __repr__(self):
            return str(self.value)   

    class ScanWorkflow(__base_enum):
        PR = "pr"
        PUSH = "push"

    class FeedbackWorkflow(__base_enum):
        PR = "pr"

    class ScanStates(__base_enum):
        AWAIT = "await"
        FEEDBACK = "feedback"
        ANNOTATE = "annotate"

    EXCHANGE_SCAN_INPUT = "Scan In"
    EXCHANGE_SCAN_WAIT = "Scan Await"
    EXCHANGE_SCAN_FEEDBACK = "Scan Feedback"
    EXCHANGE_SCAN_POLLING = "Scan Polling Delivery"

    QUEUE_SCAN_POLLING = "Polling Scans"
    QUEUE_SCAN_WAIT = "Awaited Scans"
    QUEUE_FEEDBACK_PR = "PR Feedback"

    ROUTEKEY_SCAN_WAIT = F"{ScanStates.AWAIT}.*.*"
    ROUTEKEY_FEEDBACK_PR = f"{ScanStates.FEEDBACK}.{FeedbackWorkflow.PR}.*"

    @staticmethod
    def get_poll_binding_topic(moniker):
        return f"{WorkflowStateService.ScanStates.AWAIT}.*.{moniker}"

    @staticmethod
    def get_poll_queue_name(moniker):
        return f"{WorkflowStateService.QUEUE_SCAN_POLLING}.{moniker}"

    
    @staticmethod
    def log():
        return logging.getLogger("WorkflowStateService")

    def __init__(self, moniker, amqp_url , amqp_user, amqp_password, ssl_verify, pr_workflow : WorkflowBase):
        self.__lock = asyncio.Lock()
        self.__amqp_url = amqp_url
        self.__amqp_user = amqp_user
        self.__amqp_password = amqp_password
        self.__ssl_verify = ssl_verify
        self.__client = None
        self.__pr_workflow = pr_workflow
        self.__service_moniker = moniker

        netloc = urllib.parse.urlparse(self.__amqp_url).netloc

        if '@' in netloc:
            SecretRegistry.register(netloc.split("@")[0])

    
    @property
    def use_ssl(self):
        return urllib.parse.urlparse(self.__amqp_url).scheme == "amqps"


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
    

    async def start_pr_scan_workflow(self, scanid : str) -> None:
        await self.__pr_workflow.scan_start(await self.mq_client(), self.__service_moniker, scanid)

