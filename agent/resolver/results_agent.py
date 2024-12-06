from workflows.base_service import BaseWorkflowService
from workflows.messaging.v1.delegated_scan import DelegatedScanResultMessage
from services import CxOneFlowServices
from api_utils.auth_factories import EventContext
from orchestration.base import OrchestratorBase
from orchestration import OrchestrationDispatch
from workflows.utils import AdditionalScanContentWriter
import aio_pika, gzip
from typing import List

class ResolverResultsAgent(BaseWorkflowService):

    def __init__(self, services : CxOneFlowServices):
        self.__services = services

    @staticmethod
    def __orchestrator_factory(orchestrator_name : str, context : EventContext) -> OrchestratorBase:

        module_name = ".".join(orchestrator_name.split(".")[:-1])
        class_name = orchestrator_name.split(".")[-1:].pop()
        module = __import__(module_name)
        return getattr(module, class_name)(context)
    
    @staticmethod
    def __additional_content_factory(resolver_content : bytearray, container_content : bytearray) -> List[AdditionalScanContentWriter]:
        ret_val = []
        if resolver_content is not None:
            ret_val.append(AdditionalScanContentWriter("/.cxsca-results.json", resolver_content, gzip.decompress))

        if container_content is not None:
            ret_val.append(AdditionalScanContentWriter("/containers-resolution.json", container_content, gzip.decompress))

    async def __call__(self, msg : aio_pika.abc.AbstractIncomingMessage):
        result_msg = await self._safe_deserialize_body(msg, DelegatedScanResultMessage)
        try:
            if not self.__services.resolver.signature_valid(result_msg.details_signature, result_msg.details.to_binary()):
                ResolverResultsAgent.log().error(f"Message signature is invalid, scan not processed for project {result_msg.details.project_name}" \
                                                 + f" with clone url {result_msg.details.clone_url} on service moniker {result_msg.moniker}.")
            else:
                # Execute just like an event message was received.
                await OrchestrationDispatch.execute_deferred_scan (
                    ResolverResultsAgent.__orchestrator_factory(result_msg.details.orchestrator, result_msg.details.event_context),
                    ResolverResultsAgent.__additional_content_factory(result_msg.resolver_results, result_msg.container_results))
           
            await msg.ack()
        except BaseException as ex:
            self.log().exception(ex)
            await msg.nack(requeue=False)
