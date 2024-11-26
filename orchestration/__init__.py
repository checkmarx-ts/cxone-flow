from api_utils import verify_signature
from .base import OrchestratorBase
import logging
from config import CxOneFlowConfig, RouteNotFoundException


class OrchestrationDispatch:

    @staticmethod
    def log():
        return logging.getLogger("OrchestrationDispatch")


    @staticmethod
    async def execute(orchestrator : OrchestratorBase):

        if orchestrator.is_diagnostic:
            return 204

        try:
            OrchestrationDispatch.log().debug(f"Service lookup: {orchestrator.route_urls}")
            cxone_service, scm_service, pr_service, resolver_service = CxOneFlowConfig.retrieve_services_by_route(orchestrator.route_urls, 
                                                                                                                  orchestrator.config_key)
            OrchestrationDispatch.log().debug(f"Service lookup success: {orchestrator.route_urls}")

            if await orchestrator.is_signature_valid(scm_service.shared_secret):
                return await orchestrator.execute(cxone_service, scm_service, pr_service, resolver_service)
            else:
                OrchestrationDispatch.log().warning(f"Payload signature validation failed, webhook payload ignored.")
        except RouteNotFoundException as ex:
            OrchestrationDispatch.log().warning(f"Event [{orchestrator.event_name}] not handled for SCM [{orchestrator.config_key}]")





