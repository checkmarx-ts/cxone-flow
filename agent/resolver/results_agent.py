from workflows.base_service import CxOneFlowAbstractWorkflowService
from workflows.messaging import DelegatedScanResultMessage
from services import CxOneFlowServices
from api_utils.auth_factories import EventContext
from orchestration.base import AbstractOrchestrator
from orchestration import OrchestrationDispatch
from workflows import ScanStates
import aio_pika, gzip, importlib
from typing import List

class ResolverResultsAgent(CxOneFlowAbstractWorkflowService):

    def __init__(self, services : CxOneFlowServices):
        self.__services = services


    @staticmethod
    def __orchestrator_factory(orchestrator_name : str, context : EventContext) -> AbstractOrchestrator:
        class_name = orchestrator_name.split(".")[-1:].pop()
        module = importlib.import_module(".".join(orchestrator_name.split(".")[:-1]))
        return getattr(module, class_name)(context)
    
    async def __call__(self, msg : aio_pika.abc.AbstractIncomingMessage):
        result_msg = await self._safe_deserialize_body(msg, DelegatedScanResultMessage)
        try:
            if not self.__services.resolver.signature_valid(result_msg.details_signature, result_msg.details.to_binary()):
                ResolverResultsAgent.log().error(f"Message signature is invalid, scan not processed for project {result_msg.details.project_name}" \
                                                 + f" with clone url {result_msg.details.clone_url} on service moniker {result_msg.moniker}.")
            else:
                # Execute just like an event message was received.
                if result_msg.state == ScanStates.FAILURE:
                    if result_msg.scan_id is not None:
                        ResolverResultsAgent.log().warning(f"Delegated scan correlation_id {result_msg.correlation_id} indicated a soft failure with exit code {result_msg.resolver_exit_code}, scanning anyway.")
                    else:
                        ResolverResultsAgent.log().error(f"Delegated scan correlation_id {result_msg.correlation_id} indicated a hard failure with exit code {result_msg.resolver_exit_code}, no scan executed.")
                
                self.__services.resolver.capture_logs(result_msg.logs)

                if result_msg.scan_id is not None:
                    ResolverResultsAgent.log().info(await OrchestrationDispatch.dispatch_delegated_scan_workflow (
                        ResolverResultsAgent.__orchestrator_factory(result_msg.details.orchestrator, result_msg.details.event_context), result_msg.scan_id))
           
            await msg.ack()
        except BaseException as ex:
            self.log().exception(ex)
            await msg.nack(requeue=False)
