import aio_pika
from typing import List
from . import ResultSeverity, ResultStates


class AbstractFeedbackWorkflow:
    @property
    def excluded_severities(self) -> List[ResultSeverity]:
        raise NotImplementedError("excluded_severities")

    @property
    def excluded_states(self) -> List[ResultStates]:
        raise NotImplementedError("excluded_states")

    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        raise NotImplementedError("workflow_start")
   
    async def is_enabled(self):
        raise NotImplementedError("is_enabled")
    
    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, **kwargs):
        raise NotImplementedError("feedback_start")
        
    async def annotation_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, projectid : str, scanid : str, annotation : str, **kwargs):
        raise NotImplementedError("annotation_start")
    


