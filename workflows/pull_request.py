import aio_pika, logging, pamqp.commands
from datetime import timedelta
from .state_service import WorkflowStateService
from .workflow_base import WorkflowBase
from .messaging import ScanAwaitMessage
from .messaging.util import compute_drop_by_timestamp


class PullRequestWorkflow(WorkflowBase):


    @staticmethod
    def log():
        return logging.getLogger("PullRequestWorkflow")


    def __init__(self, enabled : bool = False, interval_seconds : int = 90, max_interval_seconds : int = 600, backoff_scalar : int = 2, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__max_interval = timedelta(seconds=max_interval_seconds)
        self.__backoff = backoff_scalar
        self.__scan_timeout = timedelta(hours=scan_timeout)

    
    def __await_msg_factory(self, scanid : str, moniker : str) -> aio_pika.Message:
        
        return aio_pika.Message(ScanAwaitMessage(scanid=scanid, drop_by=compute_drop_by_timestamp(self.__scan_timeout), moniker=moniker, 
                                                 state=WorkflowStateService.ScanStates.AWAIT, 
                                                 workflow=WorkflowStateService.ScanWorkflow.PR).to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                 expiration=self.__interval)


    async def scan_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        topic = f"{WorkflowStateService.ScanStates.AWAIT}.{WorkflowStateService.ScanWorkflow.PR}.{moniker}"
        async with mq_client.channel() as channel:

            exchange = await channel.get_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT)

            if exchange:
                result = await exchange.publish(self.__await_msg_factory(scanid, moniker), routing_key = topic)

                stub = f"pull request workflow for scan id {scanid} on service {moniker}: {result}"

                if result == pamqp.commands.Basic.Ack:
                    PullRequestWorkflow.log().debug(f"Started {stub}")
                else:
                    PullRequestWorkflow.log().error(f"Unable to start {stub}")
