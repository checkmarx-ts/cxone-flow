from dataclasses import dataclass
from workflows.resolver_workflow import ResolverScanningWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging.v1.delegated_scan import DelegatedScanMessage, DelegatedScanResultMessage
from workflows import ScanStates
from scm_services.cloner import Cloner
from typing import Tuple
from .exceptions import ResolverAgentException
import aio_pika, pickle

@dataclass(frozen=True)
class ResolverOpts:
      persistent_log_path : str
      fail_on_manifest_failure : bool
      verbose_logging : bool
      scan_containers : bool
      ssl_verify : bool
      proxy : str



class ResolverAgent(BaseWorkflowService):
    def __init__(self, tag : str, public_key : bytearray, opts : ResolverOpts, toolkit_path : str, 
                 resolver_work_path : str, resolver_path : str, amqp_args : Tuple):
        super().__init__(*amqp_args)
        self.__tag = tag
        self.__public_key = public_key
        self.__resolver_opts = opts
        self.__toolkit_path = toolkit_path
        self.__resolver_path = resolver_path
        self.__resolver_work_path = resolver_work_path.rstrip('/') + '/'


    @property
    def tag(self) -> str:
         return self.__tag

    @property
    def route_key(self) -> str:
         return f"exec.sca-resolver.scan-complete.{self.__tag}"

    async def __call__(self, msg : aio_pika.abc.AbstractIncomingMessage):
         scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)
         try:
              ResolverAgent.log().debug("Message received")
              workflow = ResolverScanningWorkflow.from_public_key(scan_msg.capture_logs, self.__public_key)

              if not workflow.validate_signature(scan_msg.details_signature, scan_msg.details.to_binary()):
                   ResolverAgent.log().error(f"Signature validation failed for tag {self.__tag} coming from service moniker {scan_msg.moniker}.")
              else:

               # Unpickle the cloner and clone
               cloner = pickle.loads(scan_msg.details.pickled_cloner)

               if not isinstance(cloner, Cloner):
                    raise ResolverAgentException.cloner_type_exception(type(cloner))
               else:
                    async with await cloner.clone(scan_msg.details.clone_url, scan_msg.details.event_context, False, self.__resolver_work_path) as clone_worker:
                         await cloner.reset_head(await clone_worker.loc(), scan_msg.details.commit_hash)

                         # TODO: Run Resolver
                         # STUB
                         import json
                         with open("test_data/.cxsca-results.json", "rt") as f:
                              sca_results = json.load(f)
                         with open("test_data/containers-resolution.json", "rt") as f:
                              container_results = json.load(f)
                              
                         result_msg = DelegatedScanResultMessage.factory(
                              moniker=scan_msg.moniker,
                              state=ScanStates.DONE,
                              workflow=scan_msg.workflow,
                              details=scan_msg.details,
                              details_signature=scan_msg.details_signature,
                              resolver_results=sca_results,
                              container_results=container_results,
                              logs="this is a log",
                              exit_code=0)
                         
                         await workflow.deliver_resolver_results(await self.mq_client(), self.route_key, result_msg, ResolverScanService.EXCHANGE_RESOLVER_SCAN)
              await msg.ack()
         except BaseException as ex:
              self.log().exception(ex)
              await msg.nack(requeue=False)
