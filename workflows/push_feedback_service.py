import aio_pika, logging
from workflows.feedback_workflow_base import AbstractFeedbackWorkflow
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.messaging import PushDetails

class PushFeedbackService(BaseWorkflowService):
    PUSH_ELEMENT_PREFIX = "push:"
    PUSH_TOPIC_PREFIX = "push."

    ROUTEKEY_FEEDBACK_PUSH = f"{BaseWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH}.*"

    EXCHANGE_SCAN_FEEDBACK = f"{BaseWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Scan Feedback"
    QUEUE_FEEDBACK_PUSH = f"{BaseWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Push Feedback"


    @staticmethod
    def log():
        return logging.getLogger("PushFeedbackService")

    @property
    def workflow(self) -> AbstractFeedbackWorkflow:
        return self.__workflow

    @staticmethod
    def make_topic(state : ScanStates, workflow : ScanWorkflow, moniker : str):
        return f"{BaseWorkflowService.TOPIC_PREFIX}{PushFeedbackService.PUSH_TOPIC_PREFIX}{state}.{workflow}.{moniker}"


    def __init__(self, moniker : str, workflow : AbstractFeedbackWorkflow, 
                 amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__workflow = workflow


    # TODO: Accept instance of Sarif module
    async def execute_sarif_delivery(self, msg : aio_pika.abc.AbstractIncomingMessage):
        ...
        # am = await self._safe_deserialize_body(msg, ScanAnnotationMessage)
        # pr_details = PRDetails.from_dict(am.workflow_details)


    # async def start_push_scan_workflow(self, projectid : str, scanid : str, details : PushDetails) -> None:
    #     ...

    async def start_sarif_feedback(self, projectid : str, scanid : str, details : PushDetails) -> None:
        await self.workflow.workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))
