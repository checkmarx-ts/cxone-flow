from .base_service import BaseWorkflowService
from . import ScanStates, ExecTypes, ResolverOps, ScanWorkflow
from .resolver_workflow_base import AbstractResolverWorkflow
from scm_services.cloner import Cloner
from typing import List,Tuple,Type
from .exceptions import WorkflowException
from .messaging import DelegatedScanMessage, DelegatedScanDetails
import urllib, re, pickle
from api_utils.auth_factories import EventContext
from cxone_api.high.projects import ProjectRepoConfig
from cxone_api.high.scans import ScanFilterConfig
from cxone_api import CxOneClient

class ResolverScanService(BaseWorkflowService):

    __tag_validation_re = re.compile("[^0-9a-zA-z-_]+")

    RESOLVER_ELEMENT_PREFIX = "res:"
    RESOLVER_TOPIC_PREFIX = "res."

    EXCHANGE_RESOLVER_SCAN = f"{BaseWorkflowService.ELEMENT_PREFIX}{RESOLVER_ELEMENT_PREFIX}SCA Resolver Scan In"
    QUEUE_RESOLVER_COMPLETE = f"{BaseWorkflowService.ELEMENT_PREFIX}{RESOLVER_ELEMENT_PREFIX}Finished Resolver Scans"
    ROUTEKEY_EXEC_SCA_SCAN_COMPLETE = f"{BaseWorkflowService.TOPIC_PREFIX}{RESOLVER_TOPIC_PREFIX}{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN_COMPLETE}.#"

    EXCHANGE_RESOLVER_SCAN_DLX = f"{BaseWorkflowService.ELEMENT_PREFIX}{RESOLVER_ELEMENT_PREFIX}SCA Resolver DLX"
    ROUTEKEY_DLX = f"{BaseWorkflowService.TOPIC_PREFIX}{RESOLVER_TOPIC_PREFIX}#"
    QUEUE_RESOLVER_TIMEOUT = f"{BaseWorkflowService.ELEMENT_PREFIX}{RESOLVER_ELEMENT_PREFIX}Resolver Timeout"

    QUEUE_RESOLVER_EXEC_STUB = f"{BaseWorkflowService.ELEMENT_PREFIX}{RESOLVER_ELEMENT_PREFIX}Resolver Req"
    ROUTEKEY_EXEC_SCA_SCAN_STUB = f"{BaseWorkflowService.TOPIC_PREFIX}{RESOLVER_TOPIC_PREFIX}{ScanStates.EXECUTE}.{ExecTypes.RESOLVER}.{ResolverOps.SCAN}"

    @staticmethod
    def __validate_tags(keys : List[str]):
        for k in keys:
            if ResolverScanService.__tag_validation_re.search(k):
                raise WorkflowException.invalid_tag(k)

    def __init__(self, moniker : str, cxone_client : CxOneClient, amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool, 
                 workflow : AbstractResolverWorkflow, default_tag : str, project_tag_key : str, allowed_agent_tags : list):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__service_moniker = moniker
        self.__default_tag = default_tag
        self.__project_tag_key = project_tag_key
        self.__workflow = workflow
        self.__client = cxone_client

        if allowed_agent_tags is not None:
            ResolverScanService.__validate_tags(allowed_agent_tags)
        self.__agent_tags = allowed_agent_tags
    
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
        return self.__agent_tags if self.__agent_tags is not None else []
    
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
    
    def signature_valid(self, signature : bytearray, payload : bytearray) -> bool:
        return self.__workflow.validate_signature(signature, payload)
    
    def capture_logs(self, logs : bytearray) -> None:
        if self.__workflow.capture_logs and logs is not None:
            self.log().info(f"Captured resolver logs: [{logs.decode()}]")
    
    async def request_resolver_scan(self, scanner_tag : str, project_config : ProjectRepoConfig, cloner : Cloner, 
                                    clone_url : str, commit_hash :str, scan_workflow : ScanWorkflow, 
                                    event_context : EventContext, orchestrator : str) -> bool:
        
        if scanner_tag not in self.agent_tags:
            raise WorkflowException.unknown_resolver_tag(scanner_tag, clone_url)
        
        # Bug workaround
        filters = (await ScanFilterConfig.from_repo_config(self.__client, project_config)).compute_filters("sca")
        if isinstance(filters, dict):
            filters = filters['filter']

        details_msg = DelegatedScanDetails(
            clone_url=clone_url, 
            commit_hash=commit_hash,
            file_filters=filters,
            project_name=project_config.name,
            pickled_cloner=pickle.dumps(cloner, protocol=pickle.HIGHEST_PROTOCOL), 
            event_context=event_context,
            orchestrator=orchestrator)
        
        msg = DelegatedScanMessage.factory(
            moniker=self.__service_moniker, 
            state=ScanStates.EXECUTE,
            workflow=scan_workflow,
            capture_logs=self.__workflow.capture_logs,
            details = details_msg,
            details_signature=self.__workflow.get_signature(details_msg))
        
        return await self.__workflow.resolver_scan_kickoff(await self.mq_client(), 
                                                           self.make_topic_for_tag(scanner_tag), 
                                                           msg, ResolverScanService.EXCHANGE_RESOLVER_SCAN)
                
    

