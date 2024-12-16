import aio_pika
from .base_workflow import AbstractAsyncWorkflow
from .messaging import DelegatedScanMessage, DelegatedScanDetails, DelegatedScanResultMessage

class AbstractResolverWorkflow(AbstractAsyncWorkflow):

    @property
    def capture_logs(self) -> bool:
        raise NotImplementedError("emit_logs")

    @property
    def is_enabled(self) -> bool:
        raise NotImplementedError("is_enabled")
    
    def get_signature(self, details : DelegatedScanDetails) -> bytearray:
        raise NotImplementedError("get_signature")

    def validate_signature(self, signature : bytearray, payload : bytearray) -> bool:
        raise NotImplementedError("validate_signature")
    
    async def deliver_resolver_results(self, mq_client : aio_pika.abc.AbstractRobustConnection, 
                                       route_key : str, msg : DelegatedScanResultMessage, exchange : str) -> bool:
        raise NotImplementedError("deliver_resolver_results")

    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanMessage, exchange : str) -> bool:
        raise NotImplementedError("resolver_scan_kickoff")
