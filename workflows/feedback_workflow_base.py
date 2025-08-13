import aio_pika
from typing import List
from workflows import ResultSeverity, ResultStates
from workflows.base_workflow import AbstractAsyncWorkflow
from workflows.messaging import ScanAwaitMessage

class AbstractFeedbackWorkflow(AbstractAsyncWorkflow):
    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs) -> None:
        raise NotImplementedError("workflow_start")

    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs) -> None:
        raise NotImplementedError("feedback_start")

    async def feedback_error(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str,
                             error_msg : str, **kwargs) -> None:
        raise NotImplementedError("feedback_start")

    async def is_enabled(self) -> bool:
        raise NotImplementedError("is_enabled")
    
    async def is_handler(self, msg : ScanAwaitMessage) -> bool:
        raise NotImplementedError("is_handler")
    
class AbstractPRFeedbackWorkflow(AbstractFeedbackWorkflow):
    @property
    def excluded_severities(self) -> List[ResultSeverity]:
        raise NotImplementedError("excluded_severities")

    @property
    def excluded_states(self) -> List[ResultStates]:
        raise NotImplementedError("excluded_states")
        
    async def annotation_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, annotation : str, **kwargs):
        raise NotImplementedError("annotation_start")
    


