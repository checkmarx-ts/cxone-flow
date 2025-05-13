from orchestration.base import OrchestratorBase
from orchestration.naming.gl import GitlabProjectNaming
from api_utils.auth_factories import EventContext
from jsonpath_ng import parse
from services import CxOneFlowServices
from scm_services import SCMService
from workflows.utils import AdditionalScanContentWriter
from typing import Dict, List
from cxone_api.high.scans import ScanInspector
from cxone_api.util import json_on_ok
import urllib, asyncio, fnmatch



class GitlabOrchestrator(OrchestratorBase):

    __no_hash = "0000000000000000000000000000000000000000"

    __push_actual_label = "actual"
    __push_delete_label = "branch_delete"
    __push_create_label = "branch_create"

    __push_event_name = "push"

    __pr_closed_states = ["closed"]

    __event_git_ssh_url_query = parse("$.project.git_ssh_url")
    __event_git_http_url_query = parse("$.project.git_http_url")
    __event_type_query = parse("$.object_kind")

    __event_project_path_query = parse("$.project.path_with_namespace")
    __event_project_id_query = parse("$.project.id")


    __push_after_hash_query = parse("$.after")
    __push_before_hash_query = parse("$.before")
    __push_ref_query = parse("$.ref")
    __push_ref_protected_query = parse("$.ref_protected")

    __pr_draft_query = parse("$.object_attributes.draft")
    __pr_link_query = parse("$.object_attributes.url")
    __pr_id_query = parse("$.object_attributes.iid")
    __pr_state_query = parse("$.object_attributes.state")
    __pr_status_query = parse("$.object_attributes.action")
    __pr_source_branch_query = parse("$.object_attributes.source_branch")
    __pr_target_branch_query = parse("$.object_attributes.target_branch")
    __pr_commit_hash_query = parse("$.object_attributes.last_commit.id")

    __api_default_branch_query = parse("$.default_branch")
    __api_protected_branch_query = parse("$[*].name")

    def __init__(self, event_context : EventContext):
        OrchestratorBase.__init__(self, event_context)

        self.__isdiagnostic = False

        if "message" in event_context.message.keys() and event_context.message['message'] == "Hello World":
            self.__isdiagnostic = True
            return
        
        event_type = GitlabOrchestrator.__event_type_query.find(event_context.message)
        if len(event_type) > 0:
            self.__event = event_type.pop().value
        else:
            self.__event = event_context.message['event_name'] \
                if 'event_name' in event_context.message.keys() else "Unknown"
            
        if self.__event == GitlabOrchestrator.__push_event_name:
            sub_event = GitlabOrchestrator.__push_actual_label
            before =  GitlabOrchestrator.__push_before_hash_query.find(event_context.message)
            if len(before) > 0:
                if before.pop().value == GitlabOrchestrator.__no_hash:
                    sub_event = GitlabOrchestrator.__push_create_label

            after =  GitlabOrchestrator.__push_after_hash_query.find(event_context.message)
            if len(after) > 0:
                if after.pop().value == GitlabOrchestrator.__no_hash:
                    sub_event = GitlabOrchestrator.__push_delete_label

            self.__event = f"{self.__event}:{sub_event}"

        self.__clone_urls = {}
        ssh_url = GitlabOrchestrator.__event_git_ssh_url_query.find(event_context.message)
        if len(ssh_url) > 0:
            self.__clone_urls['ssh'] = ssh_url.pop().value
        
        http_url = GitlabOrchestrator.__event_git_http_url_query.find(event_context.message)
        if len(http_url) > 0:
            http = http_url.pop().value
            self.__clone_urls[urllib.parse.urlparse(http).scheme] = http
        
        self.__route_urls = list(self.__clone_urls.values())

    @property
    def event_name(self) -> str:
        return self.__event

    @property
    def route_urls(self) -> list:
        return self.__route_urls

    @property
    def is_diagnostic(self) -> bool:
        return self.__isdiagnostic

    @property
    def config_key(self):
        return "gl"

    async def is_signature_valid(self, shared_secret : str) -> bool:
        return shared_secret == self.get_header_key_safe('X-Gitlab-Token')

    async def _get_target_branch_and_hash(self) -> tuple:
        return self.__target_branch, self.__target_hash

    async def _get_source_branch_and_hash(self) -> tuple:
        return self.__source_branch, self.__source_hash
    
    @property
    def _repo_project_key(self) -> str:
        return self.__repo_project_key

    @property
    def _repo_organization(self) -> str:
        return self.__repo_organization

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]
        
    @property
    def _repo_name(self) -> str:
        return self.__repo_name

    @property
    def _repo_slug(self) -> str:
        return self.__repo_project_key

    @property
    def _pr_state(self) -> str:
        return self.__pr_state

    @property
    def _pr_status(self) -> str:
        return self.__pr_status

    @property
    def _pr_id(self) -> str:
        return self.__pr_id
    
    def __populate_common_event_data(self):
        self.__repo_project_key = GitlabOrchestrator.__event_project_path_query.find(self.event_context.message).pop().value
        self.__repo_name = self.__repo_project_key.split("/")[-1:].pop()
        self.__repo_organization = "/".join(self.__repo_project_key.split("/")[:-1])

    
    async def _execute_push_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                          scan_tags : Dict[str, str]=None):

        self.__source_branch = self.__target_branch = OrchestratorBase.normalize_branch_name(
            GitlabOrchestrator.__push_ref_query.find(self.event_context.message).pop().value)
        self.__source_hash = self.__target_hash = GitlabOrchestrator.__push_after_hash_query.find(self.event_context.message).pop().value

        self.__populate_common_event_data()

        self.__protected_branches = []
        if GitlabOrchestrator.__push_ref_protected_query.find(self.event_context.message).pop().value:
            self.__protected_branches.append(OrchestratorBase.normalize_branch_name(self.__target_branch))

        return await OrchestratorBase._execute_push_scan_workflow(self, services, additional_content, scan_tags)

    async def execute(self, services : CxOneFlowServices):
        if self.__event not in GitlabOrchestrator.__workflow_map.keys():
            GitlabOrchestrator.log().error(f"Unhandled event type: {self.__event}")
            return 
        return await GitlabOrchestrator.__workflow_map[self.__event](self, services)

    async def execute_deferred(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter], scan_tags : Dict[str, str]=None):
        self.deferred_scan = True
        return await GitlabOrchestrator.__workflow_map[self.__event](self, services, additional_content, scan_tags)

    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        return self.__protected_branches
        
    async def get_default_cxone_project_name(self) -> str:
        return GitlabProjectNaming.create_project_name(self._repo_project_key)

    async def __is_pr_draft(self) -> bool:
        return bool(GitlabOrchestrator.__pr_draft_query.find(self.event_context.message).pop().value)


    def __populate_common_pr_data(self):
        self.__source_branch = OrchestratorBase.normalize_branch_name(GitlabOrchestrator.__pr_source_branch_query.find(self.event_context.message).pop().value)
        self.__target_branch = OrchestratorBase.normalize_branch_name(GitlabOrchestrator.__pr_target_branch_query.find(self.event_context.message).pop().value)
        self.__source_hash = GitlabOrchestrator.__pr_commit_hash_query.find(self.event_context.message).pop().value
        self.__target_hash = None
        self.__pr_id = str(GitlabOrchestrator.__pr_id_query.find(self.event_context.message).pop().value)
        self.__pr_state = GitlabOrchestrator.__pr_state_query.find(self.event_context.message).pop().value
        self.__pr_status = GitlabOrchestrator.__pr_status_query.find(self.event_context.message).pop().value

    async def _execute_pr_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                        scan_tags : Dict[str, str]=None) -> ScanInspector:
        if await self.__is_pr_draft():
            GitlabOrchestrator.log().info(f"Skipping draft PR {GitlabOrchestrator.__pr_link_query.find(self.event_context.message).pop().value}")
            return

        self.__populate_common_event_data()
        self.__populate_common_pr_data()

        project_id = GitlabOrchestrator.__event_project_id_query.find(self.event_context.message).pop().value

        existing_scans = await services.cxone.find_pr_scans(await services.naming.get_project_name(
            await self.get_default_cxone_project_name(), self.event_context), self.__pr_id, self.__source_hash)

        if len(existing_scans) > 0:
            # This is a scan tag update, not a scan.
            return await OrchestratorBase._execute_pr_tag_update_workflow(self, services)
        elif self.__pr_state in GitlabOrchestrator.__pr_closed_states:
            pass
        else:
            self.__protected_branches = []

            if self.__pr_state in GitlabOrchestrator.__pr_closed_states:
                self.log().warning(f"PR {self.__pr_id} is closed, ignoring.")
            else:
                default_branch_resp, protected_branch_resp = await asyncio.gather(
                    services.scm.exec("GET", f"/projects/{project_id}"),
                    services.scm.exec("GET", f"/projects/{project_id}/protected_branches"))
                
                found_default = GitlabOrchestrator.__api_default_branch_query.find(json_on_ok(default_branch_resp))

                if len(found_default) > 0:
                    self.__protected_branches.append(OrchestratorBase.normalize_branch_name(found_default.pop().value))
                
                for pbranch in GitlabOrchestrator.__api_protected_branch_query.find(json_on_ok(protected_branch_resp)):
                    branch_value = OrchestratorBase.normalize_branch_name(pbranch.value)

                    # This can be a wildcard, so add it to the list of protected branches
                    # then add the target/source branches if they match
                    self.__protected_branches.append(branch_value)

                    if fnmatch.fnmatch(self.__target_branch, branch_value):
                        self.__protected_branches.append(OrchestratorBase.normalize_branch_name(self.__target_branch))

                    if fnmatch.fnmatch(self.__source_branch, branch_value):
                        self.__protected_branches.append(OrchestratorBase.normalize_branch_name(self.__source_branch))
            
            # dedupe
            self.__protected_branches = list(set(self.__protected_branches))

            return await OrchestratorBase._execute_pr_scan_workflow(self, services, additional_content, scan_tags)

    __workflow_map = {
        f"push:{__push_actual_label}" : _execute_push_scan_workflow,
        f"push:{__push_create_label}" : _execute_push_scan_workflow,
        "merge_request" : _execute_pr_scan_workflow
    }
