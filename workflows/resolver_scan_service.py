from .base_service import BaseWorkflowService
from . import ScanStates, ExecTypes, ResolverOps
from .resolver_workflow_base import AbstractResolverWorkflow
from scm_services.cloner import Cloner
from typing import List

class ResolverScanService(BaseWorkflowService):
    EXCHANGE_RESOLVER_SCAN = "SCA Resolver Scan In"
    QUEUE_RESOLVER_EXEC = "Resolver Scan Requests"
    QUEUE_RESOLVER_COMPLETE = "Finished Resolver Scans"
    ROUTEKEY_EXEC_SCA_SCAN = f"{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN}.#"
    ROUTEKEY_EXEC_SCA_SCAN_COMPLETE = f"{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN_COMPLETE}.#"

    def __init__(self, moniker : str, amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool, 
                 workflow : AbstractResolverWorkflow, 
                 signing_key : str, default_tag : str, tag_key : str, container_handler_tags : dict, non_container_handler_tags : list):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__signing_key = signing_key
        self.__default_tag = default_tag
        self.__tag_key = tag_key
        self.__workflow = workflow
        self.__container_tags = container_handler_tags
        self.__nocontainer_tags = non_container_handler_tags
    
    @property
    def skip(self) -> bool:
        return not self.__workflow.is_enabled
    
    @property
    def tag_key(self) -> str:
        return self.__tag_key

    @property
    def default_tag(self) -> str:
        return self.__default_tag

    @property
    def agent_tags(self) -> List:
        ret_list = self.__nocontainer_tags if self.__nocontainer_tags is not None else []
        ret_list = ret_list + (list(self.__container_tags.keys()) if self.__container_tags is not None else [])

        return ret_list
    
    async def request_resolver_scan(self, scanner_tag : str, cloner : Cloner, clone_url : str) -> bool:
        return await self.__workflow.resolver_scan_kickoff(await self.mq_client(), self.__service_moniker, scanner_tag)
    

    # await self.__workflow_map[ScanWorkflow.PR].workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))
