from api_utils import verify_signature
from .bbdc import BitBucketDataCenterOrchestrator
import logging
from config import CxOneFlowConfig

class OrchestrationDispatch:

    @staticmethod
    def log():
        return logging.getLogger("OrchestrationDispatch")


    @staticmethod
    async def execute(orchestrator):

        if orchestrator.is_diagnostic:
            return 200

        OrchestrationDispatch.log().debug(f"Service lookup: {orchestrator.route_urls}")
        cxone_service, scm_service = CxOneFlowConfig.retrieve_services_by_route(orchestrator.route_urls)
        OrchestrationDispatch.log().debug(f"Service lookup success: {orchestrator.route_urls}")

        if await orchestrator.is_signature_valid(scm_service.shared_secret):
            return await orchestrator.execute(cxone_service, scm_service)
        else:
            OrchestrationDispatch.log().warn(f"Payload signature validation failed, webhook payload ignored.")




