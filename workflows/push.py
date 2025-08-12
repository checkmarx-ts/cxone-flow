import aio_pika
from datetime import timedelta
from workflows.feedback_workflow_base import AbstractFeedbackWorkflow
from workflows.push_feedback_service import PushFeedbackService
from workflows.base_service import BaseWorkflowService
from workflows import ScanStates, ScanWorkflow
from workflows.messaging.util import compute_drop_by_timestamp
from workflows.messaging import ScanAwaitMessage

class PushWorkflow(AbstractFeedbackWorkflow):

    def __init__(self, enabled : bool = False, interval_seconds : int = 60, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__scan_timeout = timedelta(hours=scan_timeout)
    
    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        topic = PushFeedbackService.make_topic(ScanStates.AWAIT, ScanWorkflow.PUSH, moniker)
        await self._publish(mq_client, topic, 
                            aio_pika.Message(ScanAwaitMessage.factory(projectid=projectid,
                                                     scanid=scanid, 
                                                     drop_by=compute_drop_by_timestamp(self.__scan_timeout), 
                                                     moniker=moniker,
                                                     state=ScanStates.AWAIT,
                                                     workflow_details=kwargs,
                                                     workflow=ScanWorkflow.PUSH).to_binary(), 
                                                     delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                     expiration=self.__interval,),
                              f"{topic} for scan id {scanid} on service {moniker}", BaseWorkflowService.EXCHANGE_SCAN_INPUT)
