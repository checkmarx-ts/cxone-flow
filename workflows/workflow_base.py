import aio_pika


class AbstractWorkflow:
    async def workflow_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        raise NotImplementedError("scan_start")
   
    async def is_enabled(self):
        raise NotImplementedError("is_enabled")
    
    async def feedback_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        raise NotImplementedError("feedback_start")
        
    async def annotation_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str, annotation : str):
        raise NotImplementedError("annotation_start")
    


