import aio_pika
from datetime import timedelta
from workflows.pr_feedback_service import PRFeedbackService
from workflows import ScanWorkflow, ScanStates, ResultSeverity, ResultStates
from workflows.feedback_workflow_base import AbstractPRFeedbackWorkflow
from workflows.messaging import ScanAwaitMessage, ScanFeedbackMessage, ScanAnnotationMessage
from workflows.messaging.util import compute_drop_by_timestamp
from workflows.base_service import CxOneFlowAbstractWorkflowService
from typing import List

class PullRequestWorkflow(AbstractPRFeedbackWorkflow):

    def __init__(self, excluded_severities : List[ResultSeverity] = [], excluded_states : List[ResultStates] = [], 
                 enabled : bool = False, interval_seconds : int = 60, scan_timeout : int = 48):
        self.__enabled = enabled
        self.__excluded_states = excluded_states
        self.__excluded_severities = excluded_severities
        self.__interval = timedelta(seconds=interval_seconds)
        self.__scan_timeout = timedelta(hours=scan_timeout)

    async def is_handler(self, msg : ScanAwaitMessage) -> bool:
        return msg.workflow == ScanWorkflow.PR

    @property
    def excluded_severities(self) -> List[ResultSeverity]:
        return self.__excluded_severities

    @property
    def excluded_states(self) -> List[ResultStates]:
        return self.__excluded_states

    def __feedback_msg_factory(
        self, projectid: str, scanid: str, moniker: str, **kwargs
    ) -> aio_pika.Message:
        return aio_pika.Message(
            ScanFeedbackMessage.factory(
                projectid=projectid,
                scanid=scanid,
                moniker=moniker,
                state=ScanStates.FEEDBACK,
                workflow=ScanWorkflow.PR,
                workflow_details=kwargs,
            ).to_binary(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

    def __annotation_msg_factory(
        self, projectid: str, scanid: str, moniker: str, annotation: str, **kwargs
    ) -> aio_pika.Message:
        return aio_pika.Message(
            ScanAnnotationMessage.factory(
                projectid=projectid,
                scanid=scanid,
                moniker=moniker,
                annotation=annotation,
                state=ScanStates.ANNOTATE,
                workflow=ScanWorkflow.PR,
                workflow_details=kwargs,
            ).to_binary(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

    def __await_msg_factory(
        self, projectid: str, scanid: str, moniker: str, **kwargs
    ) -> aio_pika.Message:
        return aio_pika.Message(
            ScanAwaitMessage.factory(
                projectid=projectid,
                scanid=scanid,
                drop_by=compute_drop_by_timestamp(self.__scan_timeout),
                moniker=moniker,
                state=ScanStates.AWAIT,
                workflow_details=kwargs,
                workflow=ScanWorkflow.PR,
            ).to_binary(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=self.__interval,
        )

    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        topic = PRFeedbackService.make_topic(ScanStates.AWAIT, ScanWorkflow.PR, moniker)
        await self._publish(mq_client, topic, self.__await_msg_factory(projectid, scanid, moniker, **kwargs), 
                            f"{topic} for scan id {scanid} on service {moniker}", CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)

    async def feedback_error(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str,
                             error_msg : str, **kwargs):
        await self.annotation_start(mq_client, moniker, projectid, scanid, error_msg, **kwargs)

    async def is_enabled(self):
        return self.__enabled

    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        topic = PRFeedbackService.make_topic(ScanStates.FEEDBACK, ScanWorkflow.PR, moniker)
        await self._publish(mq_client, topic, self.__feedback_msg_factory(projectid, scanid, moniker, **kwargs), 
                            f"{topic} for scan id {scanid} on service {moniker}", CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)

    async def annotation_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, annotation : str, **kwargs):
        topic = PRFeedbackService.make_topic(ScanStates.ANNOTATE, ScanWorkflow.PR, moniker)
        await self._publish(mq_client, topic, self.__annotation_msg_factory(projectid, scanid, moniker, annotation, **kwargs), 
                            f"{topic} for scan id {scanid} on service {moniker}", CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)
