import aio_pika

class PullRequestWorkflow:

    def __init__(self, enabled : bool = False, interval_seconds : int = 90, max_interval_seconds : int = 600, backoff_scalar : int = 2, scan_timeout : int = 48):
        self.__enabled = enabled

    async def start(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanid : str):
        pass