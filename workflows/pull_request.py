import aio_pika, logging, pamqp.commands
from datetime import timedelta
from .state_service import WorkflowStateService
from . import ScanWorkflow, ScanStates
from .workflow_base import AbstractWorkflow
from .messaging import ScanAwaitMessage
from .messaging.util import compute_drop_by_timestamp

class PullRequestWorkflow(AbstractWorkflow):


    @staticmethod
    def log():
        return logging.getLogger("PullRequestWorkflow")


    def __init__(self, enabled : bool = False, interval_seconds : int = 90, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__scan_timeout = timedelta(hours=scan_timeout)

    
    def __await_msg_factory(self, scanid : str, moniker : str) -> aio_pika.Message:
        
        return aio_pika.Message(ScanAwaitMessage(scanid=scanid, drop_by=compute_drop_by_timestamp(self.__scan_timeout), moniker=moniker, 
                                                 state=ScanStates.AWAIT, 
                                                 workflow=ScanWorkflow.PR).to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                 expiration=self.__interval)


    async def scan_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        topic = f"{ScanStates.AWAIT}.{ScanWorkflow.PR}.{moniker}"
        async with mq_client.channel() as channel:

            exchange = await channel.get_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT)

            if exchange:
                result = await exchange.publish(self.__await_msg_factory(scanid, moniker), routing_key = topic)

                stub = f"pull request workflow for scan id {scanid} on service {moniker}: {result}"

                if type(result) == pamqp.commands.Basic.Ack:
                    PullRequestWorkflow.log().debug(f"Started {stub}")
                else:
                    PullRequestWorkflow.log().error(f"Unable to start {stub}")

    
    async def is_enabled(self):
        return self.__enabled

