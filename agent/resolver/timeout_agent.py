from workflows.base_service import BaseWorkflowService
from services import CxOneFlowServices
from workflows.messaging import DelegatedScanMessage
import aio_pika

class ResolverTimeoutAgent(BaseWorkflowService):

    def __init__(self, services : CxOneFlowServices):
        self.__services = services

    async def __call__(self, msg : aio_pika.abc.AbstractIncomingMessage):
        scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)

        try:
            if not self.__services.resolver.signature_valid(scan_msg.details_signature, scan_msg.details.to_binary()):
                ResolverTimeoutAgent.log().error(f"Message signature is invalid, scan not processed for project {scan_msg.details.project_name}" \
                                                 + f" with clone url {scan_msg.details.clone_url} on service moniker {scan_msg.moniker}.")
                await msg.nack(requeue=False)

            else:
              await self.__services.resolver.handle_resolver_scan_timeout(msg)
              await msg.ack()
              
        except BaseException as ex:
            self.log().exception(ex)
            await msg.nack(requeue=False)
