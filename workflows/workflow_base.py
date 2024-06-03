import aio_pika


class AbstractWorkflow:
    async def scan_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        raise NotImplementedError("scan_start")
   
    async def is_enabled(self):
        raise NotImplementedError("is_enabled")
    


