from .base_service import BaseWorkflowService
from . import ScanStates, ExecTypes, ResolverOps, ScanWorkflow
from .resolver_workflow_base import AbstractResolverWorkflow
from scm_services.cloner import Cloner
from typing import List, Tuple
from .exceptions import WorkflowException
from .messaging.v1.delegated_scan import DelegatedScanDetails
import urllib, re, pickle
from api_utils.auth_factories import EventContext
from cxone_api.high.projects import ProjectRepoConfig
from cxone_api.high.scans import ScanFilterConfig
from cxone_api import CxOneClient

class ResolverScanService(BaseWorkflowService):


    __tag_validation_re = re.compile("[^0-9a-zA-z-_]+")

    EXCHANGE_RESOLVER_SCAN = "SCA Resolver Scan In"
    QUEUE_RESOLVER_COMPLETE = "Finished Resolver Scans"
    ROUTEKEY_EXEC_SCA_SCAN_COMPLETE = f"{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN_COMPLETE}.#"

    QUEUE_RESOLVER_EXEC_STUB = "Resolver Req"
    ROUTEKEY_EXEC_SCA_SCAN_STUB = f"{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN}"

    @staticmethod
    def __validate_tags(keys : List[str]):
        for k in keys:
            if ResolverScanService.__tag_validation_re.search(k):
                raise WorkflowException.invalid_tag(k)

    def __init__(self, moniker : str, cxone_client : CxOneClient, amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool, 
                 workflow : AbstractResolverWorkflow, default_tag : str, project_tag_key : str, 
                 container_handler_tags : dict, non_container_handler_tags : list):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__default_tag = default_tag
        self.__project_tag_key = project_tag_key
        self.__workflow = workflow
        self.__client = cxone_client

        if container_handler_tags is not None:
            ResolverScanService.__validate_tags(list(container_handler_tags.keys()))
        self.__container_tags = container_handler_tags

        if non_container_handler_tags is not None:
            ResolverScanService.__validate_tags(non_container_handler_tags)
        self.__nocontainer_tags = non_container_handler_tags
    
    @property
    def skip(self) -> bool:
        return not self.__workflow.is_enabled
    
    @property
    def project_tag_key(self) -> str:
        return self.__project_tag_key

    @property
    def default_tag(self) -> str:
        return self.__default_tag

    @property
    def agent_tags(self) -> List:
        ret_list = self.__nocontainer_tags if self.__nocontainer_tags is not None else []
        ret_list = ret_list + (list(self.__container_tags.keys()) if self.__container_tags is not None else [])

        return ret_list
    
    @staticmethod
    def make_routekey_for_tag(tag : str):
        return f"{ResolverScanService.ROUTEKEY_EXEC_SCA_SCAN_STUB}.{tag}.#"

    def make_topic_for_tag(self, tag : str):
        return f"{ResolverScanService.ROUTEKEY_EXEC_SCA_SCAN_STUB}.{tag}.{self.__service_moniker}"

    @staticmethod
    def make_queuename_for_tag(tag : str):
        return f"{ResolverScanService.QUEUE_RESOLVER_EXEC_STUB}:{urllib.parse.quote(tag)}"
    
    @property
    def queue_and_topic_tuples(self) -> List[Tuple[str, str]]:
        ret_list = []
        for tag in self.agent_tags:
            ret_list.append((ResolverScanService.make_queuename_for_tag(tag), 
                             ResolverScanService.make_routekey_for_tag(tag)))
        
        return ret_list
    
    async def request_resolver_scan(self, scanner_tag : str, project_config : ProjectRepoConfig, cloner : Cloner, clone_url : str, scan_workflow : ScanWorkflow, 
                                    event_context : EventContext) -> bool:
        
        if scanner_tag not in self.agent_tags:
            raise WorkflowException.unknown_resolver_tag(scanner_tag, clone_url)
       
        msg = DelegatedScanDetails(moniker=self.__service_moniker,
                                   state=ScanStates.EXECUTE,
                                   project_name=project_config.name,
                                   file_filters=(await ScanFilterConfig.from_repo_config(self.__client, project_config)).compute_filters("sca"),
                                   workflow=scan_workflow,
                                   clone_url=clone_url, 
                                   pickled_cloner=pickle.dumps(cloner, protocol=pickle.HIGHEST_PROTOCOL), 
                                   event_context=event_context,
                                   container_tag=None if scanner_tag not in self.__container_tags.keys() 
                                   else self.__container_tags[scanner_tag])
        
        return await self.__workflow.resolver_scan_kickoff(await self.mq_client(), 
                                                           self.make_topic_for_tag(scanner_tag), 
                                                           msg, ResolverScanService.EXCHANGE_RESOLVER_SCAN)
                
    

