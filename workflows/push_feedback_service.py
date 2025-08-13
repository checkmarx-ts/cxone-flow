import aio_pika, logging
from workflows.feedback_workflow_base import AbstractFeedbackWorkflow
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.messaging import PushDetails, ScanAwaitMessage

class PushFeedbackService(BaseWorkflowService):
    PUSH_ELEMENT_PREFIX = "push:"
    PUSH_TOPIC_PREFIX = "push."

    ROUTEKEY_GEN_SARIF = f"{BaseWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH}.*"
    EXCHANGE_SARIF_WORK = f"{BaseWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Sarif Workflows"
    QUEUE_SARIF_GEN = f"{BaseWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Generate Sarif"


    @staticmethod
    def log():
        return logging.getLogger("PushFeedbackService")

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
        await self.__workflow.workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))

    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        if msg.workflow == ScanWorkflow.PUSH:
            await self.__workflow.feedback_start(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, **(msg.workflow_details))
    
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        if msg.workflow == ScanWorkflow.PUSH:
            await self.__workflow.feedback_error(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, error_msg, **(msg.workflow_details))
