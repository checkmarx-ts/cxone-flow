from .resolver_workflow_base import AbstractResolverWorkflow
import aio_pika
from .messaging.v1.delegated_scan import DelegatedScanMessage, DelegatedScanDetails
from api_utils.signatures import AsymmetricSignatureSignerVerifier, AsymmetricSignatureVerifier
from .exceptions import WorkflowException
from typing import Any

class DummyResolverScanningWorkflow(AbstractResolverWorkflow):

    @property
    def is_enabled(self) -> bool:
        return False

    @property
    def emit_logs(self) -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    @staticmethod
    def from_private_key(emit_resolver_logs : bool, private_key : bytearray) -> Any:
        self = ResolverScanningWorkflow()
        self.__emit_logs = emit_resolver_logs
        self.__signer = self.__verifier = AsymmetricSignatureSignerVerifier.from_private_key(private_key)
        return self

    @staticmethod
    def from_public_key(emit_resolver_logs : bool, public_key : bytearray) -> Any:
        self = ResolverScanningWorkflow()
        self.__emit_logs = emit_resolver_logs
        self.__signer = None
        self.__verifier = AsymmetricSignatureVerifier.from_public_key(public_key)
        return self

    @property
    def emit_logs(self) -> bool:
        return self.__emit_logs

    @property
    def is_enabled(self) -> bool:
        return True


    def __msg_factory(self, msg : DelegatedScanMessage) -> aio_pika.Message:
        return aio_pika.Message(msg.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanDetails, exchange : str):

        if self.__signer is None:
            raise WorkflowException("The payload signature private key was not provided, can't kick off a resolver scan.")

        msg = DelegatedScanMessage(details=msg, 
                                   details_signature=self.__signer.sign(msg.to_binary()),
                                   emit_logs=self.__emit_logs)
        
        await self._publish(mq_client, route_key, self.__msg_factory(msg), "Resolver Scan Workflow", exchange)

        return True
