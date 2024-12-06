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
    def capture_logs(self) -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    @staticmethod
    def from_private_key(capture_logs : bool, private_key : bytearray) -> Any:
        self = ResolverScanningWorkflow()
        self.__capture_logs = capture_logs
        self.__signer = self.__verifier = AsymmetricSignatureSignerVerifier.from_private_key(private_key)
        return self

    @staticmethod
    def from_public_key(capture_logs : bool, public_key : bytearray) -> Any:
        self = ResolverScanningWorkflow()
        self.__capture_logs = capture_logs
        self.__signer = None
        self.__verifier = AsymmetricSignatureVerifier.from_public_key(public_key)
        return self

    @property
    def capture_logs(self) -> bool:
        return self.__capture_logs

    @property
    def is_enabled(self) -> bool:
        return True


    def __msg_factory(self, msg : DelegatedScanMessage) -> aio_pika.Message:
        return aio_pika.Message(msg.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)

    def get_signature(self, details : DelegatedScanDetails) -> bytearray:
        if self.__signer is None:
            raise WorkflowException("The payload signature private key was not provided, this instance can't sign messages.")

        return self.__signer.sign(details.to_binary())
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanMessage, exchange : str):

        
        await self._publish(mq_client, route_key, self.__msg_factory(msg), "Resolver Scan Workflow", exchange)

        return True
