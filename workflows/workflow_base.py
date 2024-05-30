import aio_pika

class WorkflowBase:
    async def scan_start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        raise NotImplementedError("scan_start")
