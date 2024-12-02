from .resolver_workflow_base import AbstractResolverWorkflow
import aio_pika, logging
from .messaging.v1.delegated_scan import DelegatedScanMessage, DelegatedScanDetails
from api_utils import signature


class DummyResolverScanningWorkflow(AbstractResolverWorkflow):
    @property
    def is_enabled() -> bool:
        return False

    @property
    def emit_logs(self) -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    __signature_alg = "sha3_512"

    def __init__(self, emit_resolver_logs : bool, signing_key : str):
        self.__emit_logs = emit_resolver_logs
        self.__signing_key = signing_key


    @property
    def emit_logs(self) -> bool:
        return self.__emit_logs

    @property
    def is_enabled(self) -> bool:
        return True


    def __msg_factory(self, msg : DelegatedScanMessage) -> aio_pika.Message:
        return aio_pika.Message(msg.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanDetails, exchange : str):

        msg = DelegatedScanMessage(details=msg, 
                                   details_signature=signature.get(ResolverScanningWorkflow.__signature_alg, self.__signing_key, msg.to_binary()),
                                   emit_logs=self.__emit_logs)
        
        await self._publish(mq_client, route_key, self.__msg_factory(msg), "Resolver Scan Workflow", exchange)

        return True
