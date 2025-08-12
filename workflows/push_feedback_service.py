import aio_pika, logging, pamqp.commands
from workflows import ScanStates, ScanWorkflow
from workflows.base_service import BaseWorkflowService


class PushFeedbackService(BaseWorkflowService):
    PUSH_ELEMENT_PREFIX = "push:"
    PUSH_TOPIC_PREFIX = "push."

    @staticmethod
    def log():
        return logging.getLogger("PushFeedbackService")

    @staticmethod
    def make_topic(state : ScanStates, workflow : ScanWorkflow, moniker : str):
        return f"{BaseWorkflowService.TOPIC_PREFIX}{PushFeedbackService.PUSH_TOPIC_PREFIX}{state}.{workflow}.{moniker}"
