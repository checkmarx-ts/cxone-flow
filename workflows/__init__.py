import asyncio, aio_pika, logging
from ssl import create_default_context, CERT_NONE
from enum import Enum
import urllib.parse
from cxoneflow_logging import SecretRegistry

class WorkflowStateService:

    class ScanWorkflow(Enum):
        PR = "pr"
        PUSH = "push"

    class FeedbackWorkflow(Enum):
        PR = "pr"

    @staticmethod
    def log():
        return logging.getLogger("WorkflowStateService")

    def __init__(self, amqp_url , amqp_user, amqp_password, ssl_verify):
        self.__lock = asyncio.Lock()
        self.__amqp_url = amqp_url
        self.__amqp_user = amqp_user
        self.__amqp_password = amqp_password
        self.__ssl_verify = ssl_verify
        self.__client = None

        netloc = urllib.parse.urlparse(self.__amqp_url).netloc

        if '@' in netloc:
            SecretRegistry.register(netloc.split("@")[0])


    
    @property
    def use_ssl(self):
        return urllib.parse.urlparse(self.__amqp_url).scheme == "amqps"


    async def mq_client(self):
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
    

    async def await_scan(self, workflow : ScanWorkflow, service_moniker : str, scanid : str) -> None:
        pass

    async def exec_scan_feedback(self, workflow : FeedbackWorkflow, service_moniker : str, scanid : str) -> None:
        pass
