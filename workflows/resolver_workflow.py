from .resolver_workflow_base import AbstractResolverWorkflow
import aio_pika, logging
from typing import Dict
from .messaging.v1.delegated_scan import DelegatedScanMessage

class DummyResolverScanningWorkflow(AbstractResolverWorkflow):
    @property
    def is_enabled() -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    def __init__(self, emit_resolver_logs : bool, additional_resolver_args : Dict):
        pass

    @property
    def is_enabled(self) -> bool:
        return True
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanner_tag : str, **kwargs):


        return True
