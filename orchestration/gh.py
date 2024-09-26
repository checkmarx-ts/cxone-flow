from .base import OrchestratorBase
from api_utils import signature
from api_utils.pagers import async_api_page_generator
from api_utils.auth_factories import EventContext
from jsonpath_ng import parse
from cxone_service import CxOneService
from scm_services import SCMService
from scm_services.cloner import CloneWorker
from workflows.state_service import WorkflowStateService
from requests import Response
from cxone_api.scanning import ScanInspector


class GithubOrchestrator(OrchestratorBase):

    __api_page_max = 100

    __event_action_query = parse("$.action")

    __install_sender_query = parse("$.sender.login")
    __install_target_query = parse("$.installation.account.login")
    __install_target_type_query = parse("$.installation.account.type")
    __install_repo_selection_query = parse("$.installation.repository_selection")
    __install_events_query = parse("$.installation.events")
    __install_permissions_query = parse("$.installation.permissions")
    __install_route_url_query = parse("$.installation.account.html_url")

       
    __push_target_branch_query = parse("$.ref")
    __push_target_hash_query = parse("$.head_commit.id")
    __push_project_key_query = parse("$.repository.name")
    __push_org_key_query = parse("$.repository.owner.name")


    __pull_target_branch_query = parse("$.pull_request.base.ref")
    __pull_target_hash_query = parse("$.pull_request.base.sha")
    __pull_source_branch_query = parse("$.pull_request.head.ref")
    __pull_source_hash_query = parse("$.pull_request.head.sha")
    __pull_id_query = parse("$.number")
    __pull_state_query = parse("$.pull_request.state")
    __pull_draft_query = parse("$.pull_request.draft")
    __pull_html_url = parse("$.pull_request.html_url")
    __pull_project_key_query = parse("$.repository.name")
    __pull_org_key_query = parse("$.repository.owner.login")
    __pull_assignee_query = parse("$.pull_request.assignee")
    __pull_assignees_query = parse("$.pull_request.assignees")
    __pull_requested_reviewers_query = parse("$.pull_request[requested_teams,requested_reviewers][*]")

    __code_event_route_url_query = parse("$.repository[clone_url,ssh_url]")
    __code_event_ssh_clone_url_query = parse("$.repository.ssh_url")
    __code_event_http_clone_url_query = parse("$.repository.clone_url")
    __code_event_default_branch_name_extract = parse("$.repository.default_branch")
    
    __branch_names_extract = parse("$.[*].name")

    __expected_events = ['pull_request', 'pull_request_review', 'push']
    __expected_permissions = {
        "contents" : "read",
        "metadata" : "read",
        "pull_requests" : "write"
    }

    __permission_weights = {
        "read" : 1,
        "write" : 2
    }


    @property
    def config_key(self):
        return "gh"

    @property
    def is_diagnostic(self) -> bool:
        return self.__isdiagnostic

    async def __log_app_install(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        sender = GithubOrchestrator.__install_sender_query.find(self.event_context.message)[0].value
        target = GithubOrchestrator.__install_target_query.find(self.event_context.message)[0].value
        target_type = GithubOrchestrator.__install_target_type_query.find(self.event_context.message)[0].value

        GithubOrchestrator.log().info(f"Install event '{self.__action}': Initiated by [{sender}] on {target_type} [{target}]")
        if self.__action in ["created", "new_permissions_accepted", "added"]:
            warned = False
            bad = False
            if not target_type == "Organization":
                GithubOrchestrator.log().warning(f"Install target '{target}' is type '{target_type}' but expected to be 'Organization'.")
                warned = True

            repo_selection = GithubOrchestrator.__install_repo_selection_query.find(self.event_context.message)[0].value
            if not repo_selection == "all":
                GithubOrchestrator.log().warning(f"Repository selection is '{repo_selection}' but expected to be 'all'.")
                warned = True
            
            events = GithubOrchestrator.__install_events_query.find(self.event_context.message)
            if len(events) == 0:
                unhandled_events = GithubOrchestrator.__expected_events
            else:
                unhandled_events = [x for x in GithubOrchestrator.__expected_events if x not in events[0].value]
            if len(unhandled_events) > 0:
                bad = True
                GithubOrchestrator.log().error(f"Event types [{",".join(unhandled_events)}] do not emit web hook events as expected.")


            permissions_not_found = dict(GithubOrchestrator.__expected_permissions)
            payload_permissions = GithubOrchestrator.__install_permissions_query.find(self.event_context.message)
            if len(payload_permissions) > 0:
                permissions = payload_permissions[0].value
                for p in permissions.keys():
                    if p in permissions_not_found.keys() and GithubOrchestrator.__permission_weights[permissions_not_found[p]] <= \
                      GithubOrchestrator.__permission_weights[permissions[p]]:
                      permissions_not_found.pop(p)
            
            if len(permissions_not_found) > 0:
                bad = True
                GithubOrchestrator.log().error(f"Missing expected permissions {permissions_not_found}.")

            if warned:
                GithubOrchestrator.log().warning("Events will still be handled but the scope of repositories covered may not be as expected.")

            if bad:
                GithubOrchestrator.log().error("The GitHub app may be misconfigured, workflows will likely not work as expected.")

            if not bad and not warned:
                GithubOrchestrator.log().info("The GitHub app appears to be properly configured.")

    def __installation_route_urls(self):
        return [GithubOrchestrator.__install_route_url_query.find(self.event_context.message)[0].value]
    
    def __code_event_route_urls(self):
        return [GithubOrchestrator.__code_event_route_url_query.find(self.event_context.message)[0].value]

    def __code_event_clone_urls(self):
        return {
            "ssh" : GithubOrchestrator.__code_event_ssh_clone_url_query.find(self.event_context.message)[0].value,
            "http" : GithubOrchestrator.__code_event_http_clone_url_query.find(self.event_context.message)[0].value
        }

    def __init__(self, event_context : EventContext):
        OrchestratorBase.__init__(self, event_context)

        self.__isdiagnostic = False

        self.__event = self.get_header_key_safe('X-Github-Event') 

        if not self.__event is None and self.__event == "ping":
            self.__isdiagnostic = True
            return
        
        action_found = GithubOrchestrator.__event_action_query.find(self.event_context.message)
        if len(action_found) > 0:
            self.__action = action_found[0].value
            self.__dispatch_event = f"{self.__event}:{self.__action if self.__action is not None else ""}"
        else:
            self.__dispatch_event = self.__event

   
        self.__route_urls = GithubOrchestrator.__route_url_parser_dispatch_map[self.__event](self) \
            if self.__event in GithubOrchestrator.__route_url_parser_dispatch_map.keys() else []

        self.__clone_urls = GithubOrchestrator.__clone_url_parser_dispatch_map[self.__event](self) \
            if self.__event in GithubOrchestrator.__clone_url_parser_dispatch_map.keys() else {}


    async def execute(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        if self.__dispatch_event not in GithubOrchestrator.__workflow_map.keys():
            GithubOrchestrator.log().error(f"Unhandled event type: {self.__dispatch_event}")
        else:
            return await GithubOrchestrator.__workflow_map[self.__dispatch_event](self, cxone_service, scm_service, workflow_service)

    async def _get_clone_worker(self, scm_service : SCMService, clone_url : str, failures : int) -> CloneWorker:
        return scm_service.cloner.clone(clone_url, self.event_context, failures > 0)

    async def _get_target_branch_and_hash(self) -> tuple:
        return self.__target_branch, self.__target_hash

    async def _get_source_branch_and_hash(self) -> tuple:
        return self.__source_branch, self.__source_hash


    @property
    def route_urls(self) -> list:
        return self.__route_urls

    async def is_signature_valid(self, shared_secret : str) -> bool:
        sig = self.get_header_key_safe('X-Hub-Signature-256')
        if sig is None:
            GithubOrchestrator.log().warning("X-Hub-Signature-256 header is missing, rejecting.")
            return False
        
        hashalg,hash = sig.split("=")
        payload_hash = signature.get(hashalg, shared_secret, self.event_context.raw_event_payload)

        return hash == payload_hash


    async def _execute_push_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        self.__target_branch = self.__source_branch = OrchestratorBase.normalize_branch_name(
            GithubOrchestrator.__push_target_branch_query.find(self.event_context.message)[0].value)
        self.__target_hash = self.__source_hash = GithubOrchestrator.__push_target_hash_query.find(self.event_context.message)[0].value

        self.__project_key = GithubOrchestrator.__push_project_key_query.find(self.event_context.message)[0].value
        self.__org = GithubOrchestrator.__push_org_key_query.find(self.event_context.message)[0].value
       
        return await OrchestratorBase._execute_push_scan_workflow(self, cxone_service, scm_service, workflow_service)


    def __get_pr_assignees(self):
        ret = []
        assignee = GithubOrchestrator.__pull_assignee_query.find(self.event_context.message)
        assignees = GithubOrchestrator.__pull_assignees_query.find(self.event_context.message)

        if len(assignees) > 0 and assignees[0].value is not None and len(assignees[0].value) > 0:
            ret = assignees[0].value

        if len(assignee) > 0 and assignee[0].value is not None:
            ret.append(assignee[0].value)

        return ret

    def __get_pr_reviewers(self):
        reviewers = GithubOrchestrator.__pull_requested_reviewers_query.find(self.event_context.message)
        if len(reviewers) > 0 and reviewers[0].value is not None:
            return reviewers[0].value
        
        return []

    def __populate_common_pr_data(self):
        self.__pr_html_url = GithubOrchestrator.__pull_html_url.find(self.event_context.message)[0].value
        self.__pr_id = GithubOrchestrator.__pull_id_query.find(self.event_context.message)[0].value
        self.__project_key = GithubOrchestrator.__pull_project_key_query.find(self.event_context.message)[0].value
        self.__org = GithubOrchestrator.__pull_org_key_query.find(self.event_context.message)[0].value
        self.__target_branch = GithubOrchestrator.__pull_target_branch_query.find(self.event_context.message)[0].value
        self.__source_branch = GithubOrchestrator.__pull_source_branch_query.find(self.event_context.message)[0].value
        self.__target_hash = GithubOrchestrator.__pull_target_hash_query.find(self.event_context.message)[0].value
        self.__source_hash = GithubOrchestrator.__pull_source_hash_query.find(self.event_context.message)[0].value
        self.__is_draft = bool(GithubOrchestrator.__pull_draft_query.find(self.event_context.message)[0].value)
        self.__pr_state = f"{GithubOrchestrator.__pull_state_query.find(self.event_context.message)[0].value}{"-draft" if self.__is_draft else ""}"

        if len(self.__get_pr_assignees()) > 0:
            self.__pr_status = "REVIEWERS_ASSIGNED"
        elif len(self.__get_pr_reviewers()) > 0:
            self.__pr_status = "REVIEWERS_REQUESTED"
        else:
            self.__pr_status = "NO_REVIEWERS"


    async def _execute_pr_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService) -> ScanInspector:
        self.__populate_common_pr_data()

        if self.__is_draft:
            GithubOrchestrator.log().info(f"Skipping draft PR {self.__pr_id}: {self.__pr_html_url}")
            return
        
        return await OrchestratorBase._execute_pr_scan_workflow(self, cxone_service, scm_service, workflow_service)

    async def _execute_pr_tag_update_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        self.__populate_common_pr_data()
        return await OrchestratorBase._execute_pr_tag_update_workflow(self, cxone_service, scm_service, workflow_service)

    @property
    def _pr_id(self) -> str:
        return str(self.__pr_id)

    @property
    def _pr_state(self) -> str:
        return self.__pr_state

    @property
    def _pr_status(self) -> str:
        return self.__pr_status


    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        ret_branches = []
        def data_extractor(resp : Response):
            if resp.ok:
                json = resp.json()
                v = [b.value for b in GithubOrchestrator.__branch_names_extract.find(json)]
                return v, len(v) < GithubOrchestrator.__api_page_max

            return None

        def args_gen(offset : int):
            return { 
                "method" : "GET",
                "path" : f"/repos/{self._repo_organization}/{self._repo_project_key}/branches",
                "query" : { "protected" : True, "per_page" : GithubOrchestrator.__api_page_max, "page" : offset + 1},
                "event_context" : self.event_context
            }

        async for branch in async_api_page_generator(scm_service.exec, data_extractor, args_gen):
            ret_branches.append(branch)

        if len(ret_branches) == 0:
            ret_branches.append(GithubOrchestrator.__code_event_default_branch_name_extract.find(self.event_context.message)[0].value)

        return ret_branches

    @property
    def _repo_project_key(self) -> str:
        return self.__project_key

    @property
    def _repo_organization(self) -> str:
        return self.__org

    @property
    def _repo_slug(self) -> str:
        return self._repo_project_key

    @property
    def _repo_name(self) -> str:
        return self._repo_project_key

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]

    async def get_cxone_project_name(self) -> str:
        return f"{self._repo_organization}/{self._repo_slug}"


    __workflow_map = {
        "installation:deleted" : __log_app_install,
        "installation:unsuspend" : __log_app_install,
        "installation:suspend" : __log_app_install,
        "installation:created" : __log_app_install,
        "installation_repositories:deleted" : __log_app_install,
        "installation_repositories:unsuspend" : __log_app_install,
        "installation_repositories:suspend" : __log_app_install,
        "installation_repositories:created" : __log_app_install,
        "push" : _execute_push_scan_workflow,
        "pull_request:opened" : _execute_pr_scan_workflow,
        "pull_request:synchronize" : _execute_pr_scan_workflow,
        "pull_request:ready_for_review" : _execute_pr_scan_workflow,
        "pull_request:reopened" : _execute_pr_scan_workflow,
        "pull_request:assigned" : _execute_pr_tag_update_workflow,
        "pull_request:unassigned" : _execute_pr_tag_update_workflow,
        "pull_request:review_request_removed" : _execute_pr_tag_update_workflow,
        "pull_request:review_requested" : _execute_pr_tag_update_workflow,
        "pull_request:closed" : _execute_pr_tag_update_workflow,
        "pull_request:converted_to_draft" : _execute_pr_tag_update_workflow
        
    }

    __route_url_parser_dispatch_map = {
        "installation" : __installation_route_urls,
        "installation_repositories" : __installation_route_urls,
        "push" : __code_event_route_urls,
        "pull_request" : __code_event_route_urls

    }

    __clone_url_parser_dispatch_map = {
        "push" : __code_event_clone_urls,
        "pull_request" : __code_event_clone_urls
    }

