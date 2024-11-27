import aio_pika

class AbstractResolverWorkflow:

    @property
    def is_enabled(self) -> bool:
        raise NotImplementedError("is_enabled")

    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanner_tag : str, **kwargs) -> bool:
        raise NotImplementedError("request_scan")
