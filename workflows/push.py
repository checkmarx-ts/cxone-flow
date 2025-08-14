import aio_pika
from datetime import timedelta
from workflows.feedback_workflow_base import AbstractFeedbackWorkflow
from workflows.push_feedback_service import PushFeedbackService
from workflows.base_service import CxOneFlowAbstractWorkflowService
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.messaging.util import compute_drop_by_timestamp
from workflows.messaging import ScanAwaitMessage, ScanFeedbackMessage

class PushWorkflow(AbstractFeedbackWorkflow):

    def __init__(self, enabled : bool = False, interval_seconds : int = 60, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__interval = timedelta(seconds=interval_seconds)
        self.__scan_timeout = timedelta(hours=scan_timeout)

    async def is_enabled(self) -> bool:
        return self.__enabled

    async def is_handler(self, msg : ScanAwaitMessage) -> bool:
        return msg.workflow == ScanWorkflow.PUSH

    def __feedback_gen_msg_factory(self, moniker : str, projectid : str, scanid : str, 
                               is_error : bool = False, err_msg : str = None, **kwargs) -> ScanFeedbackMessage:
        return ScanFeedbackMessage.factory(
            projectid=projectid,
            scanid=scanid,
            moniker=moniker,
            state=ScanStates.FEEDBACK,
            workflow=ScanWorkflow.PUSH,
            workflow_details=kwargs,
            is_error = is_error,
            error_msg = err_msg
        )

    async def __publish_feedback_msg(self, mq_client : aio_pika.abc.AbstractRobustConnection, msg : ScanFeedbackMessage, msg_type : str ) -> None:
        topic = PushFeedbackService.make_topic(ScanStates.FEEDBACK, FeedbackWorkflow.PUSH_GEN, msg.moniker)
        await self._publish(mq_client, topic, 
            aio_pika.Message(msg.to_binary(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,),
            f"{msg_type}: {topic} for scan id {msg.scanid} on service {msg.moniker}", CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)

    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs) -> None:
        await self.__publish_feedback_msg(mq_client, self.__feedback_gen_msg_factory(moniker, projectid, scanid, **kwargs), "Sarif Gen")

    async def feedback_error(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str,
                             error_msg : str, **kwargs) -> None:
        await self.__publish_feedback_msg(mq_client, self.__feedback_gen_msg_factory(moniker, projectid, scanid, True, error_msg, **kwargs), "Sarif Gen Error")
    
    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        topic = PushFeedbackService.make_topic(ScanStates.AWAIT, FeedbackWorkflow.PUSH_GEN, moniker)
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
                              f"Sarif workflow start: {topic} for scan id {scanid} on service {moniker}", CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)
