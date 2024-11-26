from .resolver_workflow_base import AbstractResolverWorkflow
import aio_pika, logging
from typing import Dict

class DummyResolverScanningWorkflow(AbstractResolverWorkflow):
    @property
    def is_enabled() -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    def __init__(self, emit_resolver_logs : bool, additional_resolver_args : Dict):
        pass

    @staticmethod
    def log():
        return logging.getLogger("ResolverScanningWorkflow")

    @property
    def is_enabled() -> bool:
        return True
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, scanner_tag : str, **kwargs):
        return True
