import aio_pika
from .base_workflow import AbstractAsyncWorkflow
from .messaging.v1.delegated_scan import DelegatedScanDetails

class AbstractResolverWorkflow(AbstractAsyncWorkflow):

    @property
    def emit_logs(self) -> bool:
        raise NotImplementedError("emit_logs")

    @property
    def is_enabled(self) -> bool:
        raise NotImplementedError("is_enabled")

    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanDetails, exchange : str) -> bool:
        raise NotImplementedError("request_scan")
