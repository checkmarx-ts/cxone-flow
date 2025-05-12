from orchestration.base import OrchestratorBase
from orchestration.naming.bbdc import BitbucketProjectNaming
from api_utils.auth_factories import EventContext
from api_utils import signature
from jsonpath_ng import parse
from .exceptions import OrchestrationException
from scm_services import SCMService
from cxone_api.high.scans import ScanInspector
from services import CxOneFlowServices
from typing import List, Dict
from workflows.utils import AdditionalScanContentWriter

class BitBucketDataCenterOrchestrator(OrchestratorBase):

    __push_route_urls_query = parse("$.repository.links.clone[*]")
    __push_repo_project_key_query = parse("$.repository.project.key")
    __push_repo_project_name_query = parse("$.repository.project.name")
    __push_repo_slug_query = parse("$.repository.slug")
    __push_repo_name_query = parse("$.repository.name")
    __push_changes_extract_query = parse("$.changes[*]")
    __push_change_types_query = parse("$.changes[*].type")
    __push_scannable_change_types = ['ADD', 'UPDATE']

    __pr_route_urls_query = parse("$.pullRequest.fromRef.repository.links.clone[*]")
    __pr_draft_query = parse("$.pullRequest.draft")
    __pr_self_link_query = parse("$.pullRequest.links['self'][*]['href']")
    __pr_toref_extract_query = parse("$.pullRequest.toRef")
    __pr_fromref_extract_query = parse("$.pullRequest.fromRef")
    __pr_repo_project_key_query = parse("$.pullRequest.toRef.repository.project.key")
    __pr_repo_project_name_query = parse("$.pullRequest.toRef.repository.project.name")
    __pr_repo_slug_query = parse("$.pullRequest.toRef.repository.slug")
    __pr_repo_name_query = parse("$.pullRequest.toRef.repository.name")
    __pr_id_query = parse("$.pullRequest.id")
    __pr_reviewer_status_query = parse("$.pullRequest.reviewers[*].status")
    __pr_state_query = parse("$.pullRequest.state")


    @property
    def config_key(self):
        return "bbdc"
    

    def __init__(self, event_context : EventContext):
        OrchestratorBase.__init__(self, event_context)
        
        self.__isdiagnostic = False

        self.__event = self.get_header_key_safe('X-Event-Key') 

        if not self.__event is None and self.__event == "diagnostics:ping":
            self.__isdiagnostic = True
            return

        self.__clone_urls = {x.value['name']:x.value['href'] for x in BitBucketDataCenterOrchestrator.__push_route_urls_query.find(self.event_context.message) } | \
            {x.value['name']:x.value['href'] for x in BitBucketDataCenterOrchestrator.__pr_route_urls_query.find(self.event_context.message) }

        self.__route_urls = list(self.__clone_urls.values())

    @property
    def event_name(self) -> str:
        return self.__event


    @property
    def route_urls(self) -> list:
        return self.__route_urls

    async def is_signature_valid(self, shared_secret : str) -> bool:
        sig = self.get_header_key_safe('X-Hub-Signature')
        if sig is None:
            BitBucketDataCenterOrchestrator.log().warning("X-Hub-Signature header is missing, rejecting.")
            return False
        
        hashalg,hash = sig.split("=")
        payload_hash = signature.hmac(hashalg, shared_secret, self.event_context.raw_event_payload)

        return hash == payload_hash


    async def __workflow_dispatcher(self, dispatch_map : dict, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                    scan_tags : Dict[str, str]=None):
        if self.__event not in dispatch_map.keys():
            BitBucketDataCenterOrchestrator.log().error(f"Unhandled event type: {self.__event}")
            return 
        
        return await dispatch_map[self.__event](self, services, additional_content, scan_tags)

    async def execute(self, services : CxOneFlowServices):
        return await self.__workflow_dispatcher(BitBucketDataCenterOrchestrator.__workflow_map, services)

    async def execute_deferred(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter], scan_tags : Dict[str, str]=None):
        self.deferred_scan = True
        return await self.__workflow_dispatcher(BitBucketDataCenterOrchestrator.__workflow_map, services, additional_content, scan_tags)

    async def _execute_push_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                          scan_tags : Dict[str, str]=None):

        self.__source_branch = self.__target_branch = None
        self.__source_hash = self.__target_hash = None

        if len([x.value for x in BitBucketDataCenterOrchestrator.__push_change_types_query.find(self.event_context.message) \
                if x.value in BitBucketDataCenterOrchestrator.__push_scannable_change_types]) > 0:
            
            first_change = BitBucketDataCenterOrchestrator.__push_changes_extract_query.find(self.event_context.message)[0].value

            self.__source_branch = self.__target_branch = first_change['ref']['displayId']
            self.__source_hash = self.__target_hash = first_change['toHash']

        self.__repo_project_key = BitBucketDataCenterOrchestrator.__push_repo_project_key_query.find(self.event_context.message)[0].value
        self.__repo_project_name = BitBucketDataCenterOrchestrator.__push_repo_project_name_query.find(self.event_context.message)[0].value
        self.__repo_slug = BitBucketDataCenterOrchestrator.__push_repo_slug_query.find(self.event_context.message)[0].value
        self.__repo_name = BitBucketDataCenterOrchestrator.__push_repo_name_query.find(self.event_context.message)[0].value
        
        return await OrchestratorBase._execute_push_scan_workflow(self, services, additional_content, scan_tags)

    async def __is_pr_draft(self) -> bool:
        return bool(BitBucketDataCenterOrchestrator.__pr_draft_query.find(self.event_context.message)[0].value)
    
    def __populate_common_pr_data(self):
        toref = BitBucketDataCenterOrchestrator.__pr_toref_extract_query.find(self.event_context.message)[0].value
        self.__target_branch = toref['displayId']
        self.__target_hash = toref['latestCommit']


        fromref = BitBucketDataCenterOrchestrator.__pr_fromref_extract_query.find(self.event_context.message)[0].value
        self.__source_branch = fromref['displayId']
        self.__source_hash = fromref['latestCommit']

        self.__repo_project_key = BitBucketDataCenterOrchestrator.__pr_repo_project_key_query.find(self.event_context.message)[0].value
        self.__repo_project_name = BitBucketDataCenterOrchestrator.__pr_repo_project_name_query.find(self.event_context.message)[0].value
        self.__repo_slug = BitBucketDataCenterOrchestrator.__pr_repo_slug_query.find(self.event_context.message)[0].value
        self.__repo_name = BitBucketDataCenterOrchestrator.__pr_repo_name_query.find(self.event_context.message)[0].value
        self.__pr_id = str(BitBucketDataCenterOrchestrator.__pr_id_query.find(self.event_context.message)[0].value)
        self.__pr_state = BitBucketDataCenterOrchestrator.__pr_state_query.find(self.event_context.message)[0].value

        statuses = list(set([x.value for x in BitBucketDataCenterOrchestrator.__pr_reviewer_status_query.find(self.event_context.message)]))

        if not len(statuses) > 0:
            self.__pr_status = "NO_REVIEWERS"
        else:
            self.__pr_status = "/".join(statuses)

    async def _execute_pr_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                        scan_tags : Dict[str, str]=None) -> ScanInspector:
        if await self.__is_pr_draft():
            BitBucketDataCenterOrchestrator.log().info(f"Skipping draft PR {BitBucketDataCenterOrchestrator.__pr_self_link_query.find(self.event_context.message)[0].value}")
            return
        self.__populate_common_pr_data()
        return await OrchestratorBase._execute_pr_scan_workflow(self, services, additional_content, scan_tags)

    async def _execute_pr_tag_update_workflow(self, services : CxOneFlowServices, *args):
        if await self.__is_pr_draft():
            BitBucketDataCenterOrchestrator.log().info(f"Skipping draft PR {BitBucketDataCenterOrchestrator.__pr_self_link_query.find(self.event_context.message)[0].value}")
            return

        self.__populate_common_pr_data()

        return await OrchestratorBase._execute_pr_tag_update_workflow(self, services)


    async def _get_target_branch_and_hash(self) -> tuple:
        return self.__target_branch, self.__target_hash

    async def _get_source_branch_and_hash(self) -> tuple:
        return self.__source_branch, self.__source_hash

    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        retBranches = []
        model_resp = await scm_service.exec("GET", f"/rest/branch-utils/latest/projects/{self._repo_project_key}/repos/{self._repo_slug}/branchmodel")

        if not model_resp.ok:
            raise OrchestrationException.from_response(model_resp)

        json = model_resp.json()
        
        if 'development' in json.keys() and 'displayId' in json['development'].keys():
            retBranches.append(json['development']['displayId'])
        
        if 'production' in json.keys() and 'displayId' in json['production'].keys():
            retBranches.append(json['production']['displayId'])
        
        return list(set(retBranches))

    async def get_cxone_project_name(self) -> str:
        return BitbucketProjectNaming.create_project_name(self._repo_project_key, self.__repo_project_name, self._repo_name)

    @property
    def _pr_state(self) -> str:
        return self.__pr_state

    @property
    def _pr_status(self) -> str:
        return self.__pr_status

    @property
    def _pr_id(self) -> str:
        return self.__pr_id

    @property
    def _repo_project_key(self) -> str:
        return self.__repo_project_key

    @property
    def _repo_organization(self) -> str:
        return ""

    @property
    def _repo_slug(self) -> str:
        return self.__repo_slug

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]
        
    @property
    def _repo_name(self) -> str:
        return self.__repo_name
        
    @property
    def is_diagnostic(self) -> bool:
        return self.__isdiagnostic

    __workflow_map = {
        "repo:refs_changed" : _execute_push_scan_workflow,
        "pr:opened" : _execute_pr_scan_workflow,
        "pr:modified" : _execute_pr_scan_workflow,
        "pr:from_ref_updated" : _execute_pr_scan_workflow,
        "pr:merged" : _execute_pr_tag_update_workflow,
        "pr:declined" : _execute_pr_tag_update_workflow,
        "pr:deleted" : _execute_pr_tag_update_workflow,
        "pr:reviewer:unapproved" : _execute_pr_tag_update_workflow,
        "pr:reviewer:approved" : _execute_pr_tag_update_workflow,
        "pr:reviewer:needs_work" : _execute_pr_tag_update_workflow,
    }
