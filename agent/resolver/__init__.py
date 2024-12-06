from dataclasses import dataclass
from api_utils.signatures import AsymmetricSignatureVerifier
from workflows.base_service import BaseWorkflowService
from workflows.messaging.v1.delegated_scan import DelegatedScanMessage, DelegatedScanDetails
from typing import Tuple
from .exceptions import ResolverAgentException
import aio_pika

@dataclass(frozen=True)
class ResolverOpts:
      persistent_log_path : str
      fail_on_manifest_failure : bool
      verbose_logging : bool
      scan_containers : bool
      ssl_verify : bool
      proxy : str



class ResolverAgent(BaseWorkflowService):
    def __init__(self, tag : str, public_key : bytearray, opts : ResolverOpts, toolkit_path : str, amqp_args : Tuple):
        super().__init__(*amqp_args)
        self.__tag = tag
        self.__verifier = AsymmetricSignatureVerifier.from_public_key(public_key)
        self.__resolver_opts = opts
        self.__toolkit_path = toolkit_path

    @property
    def tag(self) -> str:
         return self.__tag

    async def __call__(self, msg : aio_pika.abc.AbstractIncomingMessage):
         scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)
         try:
              ResolverAgent.log().debug("Message received")
              # Throws an exception on signature failure.
              self.__verifier.verify(scan_msg.details_signature, scan_msg.details.to_binary())
              ResolverAgent.log().debug("Signature verified")

              # TODO: Clone

              # TODO: Run Resolver

              # TODO: Send back message
              
              await msg.ack()
         except BaseException as ex:
              self.log().exception(ex)
              await msg.nack(requeue=False)
