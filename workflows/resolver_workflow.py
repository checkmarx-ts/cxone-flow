from .resolver_workflow_base import AbstractResolverWorkflow
from .messaging import DelegatedScanMessage, DelegatedScanDetails, DelegatedScanResultMessage, DelegatedScanMessageBase
from api_utils.signatures import AsymmetricSignatureSignerVerifier, AsymmetricSignatureVerifier
from .exceptions import WorkflowException
from typing import Any, Dict
from datetime import timedelta
import aio_pika

class DummyResolverScanningWorkflow(AbstractResolverWorkflow):

    @property
    def is_enabled(self) -> bool:
        return False

    @property
    def capture_logs(self) -> bool:
        return False


class ResolverScanningWorkflow(AbstractResolverWorkflow):

    __retry_header_key = "x-remaining-retries"

    @staticmethod
    def from_private_key(capture_logs : bool, private_key : bytearray, scan_retries : int, scan_timeout_secs : int) -> Any:
        self = ResolverScanningWorkflow()
        self.__capture_logs = capture_logs
        self.__signer = self.__verifier = AsymmetricSignatureSignerVerifier.from_private_key(private_key)
        self.__scan_retries = scan_retries
        self.__scan_timeout_secs = timedelta(seconds=scan_timeout_secs)
        self.__no_kickoff = False
        return self

    @staticmethod
    def from_public_key(capture_logs : bool, public_key : bytearray) -> Any:
        self = ResolverScanningWorkflow()
        self.__capture_logs = capture_logs
        self.__signer = None
        self.__verifier = AsymmetricSignatureVerifier.from_public_key(public_key)
        self.__no_kickoff = True
        self.__scan_timeout_secs = None
        self.__scan_retries = None
        return self

    @property
    def capture_logs(self) -> bool:
        return self.__capture_logs

    @property
    def is_enabled(self) -> bool:
        return True

    def __DelegatedScanMessage_factory(self, msg : DelegatedScanMessage, retries : int) -> aio_pika.Message:
        return self.__msg_factory(msg, headers={ResolverScanningWorkflow.__retry_header_key : retries}, expiration=self.__scan_timeout_secs)

    def __msg_factory(self, msg : DelegatedScanMessageBase, **kwargs) -> aio_pika.Message:
        return self.__raw_msg_factory(msg.to_binary(), **kwargs)

    def __raw_msg_factory(self, msg : bytearray, **kwargs) -> aio_pika.Message:
        return aio_pika.Message(msg, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, **kwargs)

    def get_signature(self, details : DelegatedScanDetails) -> bytearray:
        if self.__signer is None:
            raise WorkflowException("The payload signature private key was not provided, this instance can't sign messages.")

        return self.__signer.sign(details.to_binary())

    def validate_signature(self, signature : bytearray, payload : bytearray) -> bool:
        try:
            self.__verifier.verify(signature, payload)
        except Exception as ex:
            # pylint: disable=E1205
            ResolverScanningWorkflow.log().exception("Signature validation error.", ex)
            return False
        return True
    
    async def deliver_resolver_results(self, mq_client : aio_pika.abc.AbstractRobustConnection, 
                                       route_key : str, msg : DelegatedScanResultMessage, exchange : str) -> bool:
        return await self._publish(mq_client, route_key, self.__msg_factory(msg), f"Resolver Scan Results {route_key}", exchange)
    
    async def resolver_scan_kickoff(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, 
                                    msg : DelegatedScanMessage, exchange : str) -> bool:
        if self.__no_kickoff:
            raise WorkflowException("This instance can't delegate a resolver scan.")

        return await self.resolver_scan_resubmit(mq_client, route_key, msg, exchange, self.__scan_retries)

    async def resolver_scan_resubmit(self, mq_client : aio_pika.abc.AbstractRobustConnection, route_key : str, msg : DelegatedScanMessage, exchange : str,
                                     retries : int) -> bool:
        return await self._publish(mq_client, route_key, self.__DelegatedScanMessage_factory(msg, max(retries, 0)), 
                                   f"Resolver Scan Workflow {route_key}", exchange)
        
    async def get_resolver_scan_resubmit_count(self, mq_client : aio_pika.abc.AbstractRobustConnection, msg : DelegatedScanMessage, headers : Dict) -> bool:
        if not ResolverScanningWorkflow.__retry_header_key in headers.keys():
            raise WorkflowException("Timeout message has no retry count header.")
        else:
            last_retry = headers[ResolverScanningWorkflow.__retry_header_key]
            return last_retry - 1
