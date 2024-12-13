import urllib.parse, aio_pika, logging, asyncio, os
from ssl import create_default_context, CERT_NONE
from cxoneflow_logging import SecretRegistry
from workflows.messaging.base_message import BaseMessage
from typing import Any

class BaseWorkflowService:

    ELEMENT_PREFIX = "cx:"
    TOPIC_PREFIX = "cx."

    def __init__(self, amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        self.__lock = asyncio.Lock()

        self.__amqp_url = amqp_url
        self.__amqp_user = amqp_user
        self.__amqp_password = amqp_password
        self.__ssl_verify = ssl_verify
        self.__client = None

        netloc = urllib.parse.urlparse(self.__amqp_url).netloc

        if '@' in netloc:
            SecretRegistry.register(netloc.split("@")[0])

    @staticmethod
    def log():
        return logging.getLogger("BaseWorkflowService")

    @property
    def use_ssl(self):
        return urllib.parse.urlparse(self.__amqp_url).scheme == "amqps"


    async def mq_client(self) -> aio_pika.abc.AbstractRobustConnection:
        async with self.__lock:

            if self.__client is None:
                BaseWorkflowService.log().debug(f"Creating AMQP connection to: {self.__amqp_url}")
                ctx = None

                if isinstance(self.__ssl_verify, bool):
                    if not self.__ssl_verify and self.use_ssl:
                        ctx = create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = CERT_NONE
                elif self.use_ssl:
                    if os.path.isfile(self.__ssl_verify):
                        ctx = create_default_context(cafile=self.__ssl_verify)
                    elif os.path.isdir(self.__ssl_verify):
                        ctx = create_default_context(capath=self.__ssl_verify)


                self.__client = await aio_pika.connect_robust(self.__amqp_url, \
                                                    login=self.__amqp_user, \
                                                    password=self.__amqp_password, \
                                                    ssl_context=ctx)
        return self.__client

    async def _safe_deserialize_body(self, msg : aio_pika.abc.AbstractIncomingMessage, msg_class : BaseMessage) -> Any:
        try:
            ret_val = msg_class.from_binary(msg.body)
            return ret_val
        except BaseException as ex:
            BaseWorkflowService.log().exception(ex)
            await msg.nack(requeue=False)
            raise
