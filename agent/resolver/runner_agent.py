from workflows.resolver_workflow import ResolverScanningWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging.v1.delegated_scan import DelegatedScanMessage, DelegatedScanResultMessage
from workflows import ScanStates
from scm_services.cloner import Cloner
from typing import Tuple
from .exceptions import ResolverAgentException
import aio_pika, pickle, gzip
from .resolver_opts import ResolverOpts
from _version import __version__


class ResolverRunnerAgent(BaseWorkflowService):
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
              ResolverRunnerAgent.log().debug("Message received")
              workflow = ResolverScanningWorkflow.from_public_key(scan_msg.capture_logs, self.__public_key)

              if not workflow.validate_signature(scan_msg.details_signature, scan_msg.details.to_binary()):
                   ResolverRunnerAgent.log().error(f"Signature validation failed for tag {self.__tag} coming from service moniker {scan_msg.moniker}.")
              elif not __version__ == scan_msg.details.cxoneflow_version:
                   ResolverRunnerAgent.log(). \
                         error(f"Agent version {__version__} mismatch: Scan request coming from server version {scan_msg.details.cxoneflow_version}.")
                   
                   result_msg = DelegatedScanResultMessage.factory(
                         moniker=scan_msg.moniker,
                         state=ScanStates.FAILURE,
                         workflow=scan_msg.workflow,
                         details=scan_msg.details,
                         details_signature=scan_msg.details_signature,
                         resolver_results=None,
                         container_results=None,
                         exit_code=None,
                         logs=None)

                   await workflow.deliver_resolver_results(await self.mq_client(), self.route_key, result_msg, ResolverScanService.EXCHANGE_RESOLVER_SCAN)
              else:

                    # Unpickle the cloner and clone
                    cloner = pickle.loads(scan_msg.details.pickled_cloner)

                    if not isinstance(cloner, Cloner):
                         raise ResolverAgentException.cloner_type_exception(type(cloner))
                    else:
                         async with await cloner.clone(scan_msg.details.clone_url, scan_msg.details.event_context, False, 
                                                       self.__resolver_work_path) as clone_worker:
                              await cloner.reset_head(await clone_worker.loc(), scan_msg.details.commit_hash)

                    # TODO: Run Resolver
                    # STUB
                    with open("test_data/.cxsca-results.json", "rt") as f:
                         sca_results = gzip.compress(bytes(f.read(), "UTF-8"))

                    with open("test_data/containers-resolution.json", "rt") as f:
                         container_results = gzip.compress(bytes(f.read(), "UTF-8"))

                    result_msg = DelegatedScanResultMessage.factory(
                         moniker=scan_msg.moniker,
                         state=ScanStates.DONE,
                         workflow=scan_msg.workflow,
                         details=scan_msg.details,
                         details_signature=scan_msg.details_signature,
                         resolver_results=sca_results,
                         container_results=container_results,
                         logs=None,
                         exit_code=0)

                    await workflow.deliver_resolver_results(await self.mq_client(), self.route_key, result_msg, ResolverScanService.EXCHANGE_RESOLVER_SCAN)
              await msg.ack()
         except BaseException as ex:
              self.log().exception(ex)
              await msg.nack(requeue=False)
