import aio_pika, logging, pamqp.commands, pamqp.base
from datetime import timedelta
from .state_service import WorkflowStateService
from . import ScanWorkflow, ScanStates
from .workflow_base import AbstractWorkflow
from .messaging import ScanAwaitMessage, ScanFeedbackMessage
from .messaging.util import compute_drop_by_timestamp

class PullRequestWorkflow(AbstractWorkflow):


    @staticmethod
    def log():
        return logging.getLogger("PullRequestWorkflow")


    def __init__(self, enabled : bool = False, interval_seconds : int = 90, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__scan_timeout = timedelta(hours=scan_timeout)

    def __feedback_msg_factory(self, scanid : str, moniker : str) -> aio_pika.Message:
        return aio_pika.Message(ScanFeedbackMessage(scanid=scanid, moniker=moniker, state=ScanStates.FEEDBACK,
                                                    workflow=ScanWorkflow.PR).to_binary(), 
                                                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT)

    def __annotation_msg_factory(self, scanid : str, moniker : str, annotation : str) -> aio_pika.Message:
        return aio_pika.Message(ScanFeedbackMessage(scanid=scanid, moniker=moniker, annotation=annotation, state=ScanStates.FEEDBACK,
                                                    workflow=ScanWorkflow.PR).to_binary(), 
                                                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    
    def __await_msg_factory(self, scanid : str, moniker : str) -> aio_pika.Message:
        
        return aio_pika.Message(ScanAwaitMessage(scanid=scanid, drop_by=compute_drop_by_timestamp(self.__scan_timeout), moniker=moniker, 
                                                 state=ScanStates.AWAIT, 
                                                 workflow=ScanWorkflow.PR).to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                 expiration=self.__interval)

    @staticmethod
    def __log_publish_result(result : pamqp.base.Frame, topic : str, scanid : str, moniker : str):
        stub = f"{topic} for scan id {scanid} on service {moniker}: {result}"

        if type(result) == pamqp.commands.Basic.Ack:
            PullRequestWorkflow.log().debug(f"Started {stub}")
        else:
            PullRequestWorkflow.log().error(f"Unable to start {stub}")

    async def __publish(self, mq_client : aio_pika.abc.AbstractRobustConnection, topic : str, body : bytearray, scanid : str, moniker : str):
        async with mq_client.channel() as channel:
            exchange = await channel.get_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT)

            if exchange:
                PullRequestWorkflow.__log_publish_result(await exchange.publish(body, routing_key = topic),
                                                         topic, scanid, moniker)

    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        topic = f"{ScanStates.AWAIT}.{ScanWorkflow.PR}.{moniker}"
        await self.__publish(mq_client, topic, self.__await_msg_factory(scanid, moniker).to_binary(), scanid, moniker)
    
    async def is_enabled(self):
        return self.__enabled

    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        topic = f"{ScanStates.FEEDBACK}.{ScanWorkflow.PR}.{moniker}"
        await self.__publish(mq_client, topic, self.__feedback_msg_factory(scanid, moniker).to_binary(), scanid, moniker)
        
    async def annotation_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str, annotation : str):
        topic = f"{ScanStates.ANNOTATE}.{ScanWorkflow.PR}.{moniker}"
        await self.__publish(mq_client, topic, self.__annotation_msg_factory(scanid, moniker, annotation).to_binary(), scanid, moniker)


