import aio_pika
from datetime import timedelta, datetime, UTC
from .state_service import WorkflowStateService
from .workflow_base import WorkflowBase

class PullRequestWorkflow(WorkflowBase):

    __max_iso = "9999-12-31T00:00:00Z"

    def __init__(self, enabled : bool = False, interval_seconds : int = 90, max_interval_seconds : int = 600, backoff_scalar : int = 2, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__max_interval = timedelta(seconds=max_interval_seconds)
        self.__backoff = backoff_scalar
        self.__scan_timeout = timedelta(hours=scan_timeout)

    
    def __await_msg_factory(self, scanid : str) -> aio_pika.Message:

        dropat = PullRequestWorkflow.__max_iso

        if self.__scan_timeout.total_seconds():
            dropat = (datetime.now(UTC) + self.__scan_timeout).isoformat()
        
        return aio_pika.Message(scanid.encode('UTF-8'), headers = {"x-cxoneflow-dropby" : dropat}, delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                               expiration=self.__interval)


    async def scan_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        topic = f"{WorkflowStateService.ScanStates.AWAIT}.{WorkflowStateService.ScanWorkflow.PR}.{moniker}"
        async with mq_client.channel() as channel:

            exchange = await channel.get_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT)

            if exchange:
                result = await exchange.publish(self.__await_msg_factory(scanid), routing_key = topic)
                pass
