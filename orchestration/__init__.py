from api_utils import verify_signature
from .base import OrchestratorBase
from .kickoff import KickoffOrchestrator
import logging
from config import RouteNotFoundException
from config.server import CxOneFlowConfig
from typing import List, Dict, Tuple, Union
from workflows.utils import AdditionalScanContentWriter
from cxoneflow_kickoff_api import KickoffResponseMsg


class OrchestrationDispatch:
    class NotAuthorizedException(BaseException):...

    @staticmethod
    def log():
        return logging.getLogger("OrchestrationDispatch")
    
    
    @staticmethod
    async def execute(orchestrator : OrchestratorBase):

        if orchestrator.is_diagnostic:
            return 204

        try:
            OrchestrationDispatch.log().debug(f"Service lookup: {orchestrator.route_urls}")
            services = CxOneFlowConfig.retrieve_services_by_route(orchestrator.route_urls, orchestrator.config_key)
            OrchestrationDispatch.log().debug(f"Service lookup success: {orchestrator.route_urls}")

            if await orchestrator.is_signature_valid(services.scm.shared_secret):
                return await orchestrator.execute(services)
            else:
                OrchestrationDispatch.log().warning(f"Payload signature validation failed, webhook payload ignored.")
        except RouteNotFoundException as ex:
            OrchestrationDispatch.log().warning(f"Event [{orchestrator.event_name}] not handled for SCM [{orchestrator.config_key}]")

    @staticmethod
    async def execute_deferred_scan(orchestrator : OrchestratorBase, additional_scan_contant : List[AdditionalScanContentWriter],
                                    additional_scan_tags : Dict[str, str]):
        try:
            OrchestrationDispatch.log().debug(f"Service lookup: {orchestrator.route_urls}")
            services = CxOneFlowConfig.retrieve_services_by_route(orchestrator.route_urls, orchestrator.config_key)
            OrchestrationDispatch.log().debug(f"Service lookup success: {orchestrator.route_urls}")

            return await orchestrator.execute_deferred(services, additional_scan_contant, additional_scan_tags)
        except RouteNotFoundException as ex:
            OrchestrationDispatch.log().warning(f"Deferred scan for [{orchestrator.event_name}] not handled for SCM [{orchestrator.config_key}]")

    @staticmethod
    async def execute_kickoff(orchestrator : KickoffOrchestrator) -> bool:
        try:
            OrchestrationDispatch.log().debug(f"Service lookup: {orchestrator.route_urls}")
            services = CxOneFlowConfig.retrieve_services_by_route(orchestrator.route_urls, orchestrator.config_key)
            OrchestrationDispatch.log().debug(f"Service lookup success: {orchestrator.route_urls}")
            
            if not await orchestrator.valid_bearer_token(services.kickoff):
                OrchestrationDispatch.log().error(f"{services.cxone.moniker}: Invalid bearer token sent for kickoff scan with SCM [{orchestrator.config_key}]")
                raise OrchestrationDispatch.NotAuthorizedException()
            
            return await orchestrator.execute(services)

        except RouteNotFoundException as ex:
            OrchestrationDispatch.log().warning(f"Event [{orchestrator.event_name}] not handled for SCM [{orchestrator.config_key}]")
            raise ex
