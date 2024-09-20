from .base import OrchestratorBase
from api_utils import signature
from jsonpath_ng import parse
import logging, json
from cxone_service import CxOneService
from scm_services import SCMService, Cloner
from workflows.state_service import WorkflowStateService


class GithubOrchestrator(OrchestratorBase):
    __install_action_query = parse("$.action")
    __install_sender_query = parse("$.sender.login")
    __install_target_query = parse("$.installation.account.login")
    __install_target_type_query = parse("$.installation.account.type")
    __install_repo_selection_query = parse("$.installation.repository_selection")
    __install_events_query = parse("$.installation.events")
    __install_permissions_query = parse("$.installation.permissions")
    __install_route_url_query = parse("$.installation.account.html_url")

    __push_route_url_query = parse("$.repository[clone_url,ssh_url]")
    __push_ssh_clone_url_query = parse("$.repository.ssh_url")
    __push_http_clone_url_query = parse("$.repository.clone_url")
    __push_target_branch_query = parse("$.ref")
    __push_target_hash_query = parse("$.head_commit.id")
    __push_project_key_query = parse("$.repository.name")
    __push_org_key_query = parse("$.repository.owner.name")

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


    @staticmethod
    def log():
        return logging.getLogger("BitBucketDataCenterOrchestrator")

    @property
    def config_key(self):
        return "gh"

    @property
    def is_diagnostic(self) -> bool:
        return self.__isdiagnostic

    async def __log_app_install(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        action = GithubOrchestrator.__install_action_query.find(self.__json)[0].value
        sender = GithubOrchestrator.__install_sender_query.find(self.__json)[0].value
        target = GithubOrchestrator.__install_target_query.find(self.__json)[0].value
        target_type = GithubOrchestrator.__install_target_type_query.find(self.__json)[0].value

        GithubOrchestrator.log().info(f"Install event '{action}': Initiated by [{sender}] on {target_type} [{target}]")
        if action in ["created", "new_permissions_accepted", "added"]:
            warned = False
            bad = False
            if not target_type == "Organization":
                GithubOrchestrator.log().warning(f"Install target '{target}' is type '{target_type}' but expected to be 'Organization'.")
                warned = True

            repo_selection = GithubOrchestrator.__install_repo_selection_query.find(self.__json)[0].value
            if not repo_selection == "all":
                GithubOrchestrator.log().warning(f"Repository selection is '{repo_selection}' but expected to be 'all'.")
                warned = True
            
            events = GithubOrchestrator.__install_events_query.find(self.__json)
            if len(events) == 0:
                unhandled_events = GithubOrchestrator.__expected_events
            else:
                unhandled_events = [x for x in GithubOrchestrator.__expected_events if x not in events[0].value]
            if len(unhandled_events) > 0:
                bad = True
                GithubOrchestrator.log().error(f"Event types [{",".join(unhandled_events)}] do not emit web hook events as expected.")


            permissions_not_found = dict(GithubOrchestrator.__expected_permissions)
            payload_permissions = GithubOrchestrator.__install_permissions_query.find(self.__json)
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
        return [GithubOrchestrator.__install_route_url_query.find(self.__json)[0].value]
    
    def __push_route_urls(self):
        return [GithubOrchestrator.__push_route_url_query.find(self.__json)[0].value]
    
    def __push_clone_urls(self):
        return {
            "ssh" : GithubOrchestrator.__push_ssh_clone_url_query.find(self.__json)[0].value,
            "http" : GithubOrchestrator.__push_http_clone_url_query.find(self.__json)[0].value
        }

    def __init__(self, headers : dict, webhook_payload : dict):
        OrchestratorBase.__init__(self, headers, webhook_payload)

        self.__isdiagnostic = False

        self.__event = self.get_header_key_safe('X-GitHub-Event') 

        if not self.__event is None and self.__event == "ping":
            self.__isdiagnostic = True
            return
        
        self.__json = json.loads(webhook_payload)
   
        self.__route_urls = GithubOrchestrator.__route_url_parser_dispatch_map[self.__event](self) \
            if self.__event in GithubOrchestrator.__route_url_parser_dispatch_map.keys() else []

        self.__clone_urls = GithubOrchestrator.__clone_url_parser_dispatch_map[self.__event](self) \
            if self.__event in GithubOrchestrator.__clone_url_parser_dispatch_map.keys() else {}


    async def execute(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        if self.__event not in GithubOrchestrator.__workflow_map.keys():
            GithubOrchestrator.log().error(f"Unhandled event type: {self.__event}")
        else:
            return await GithubOrchestrator.__workflow_map[self.__event](self, cxone_service, scm_service, workflow_service)


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
        payload_hash = signature.get(hashalg, shared_secret, self._webhook_payload)

        return hash == payload_hash


    async def _execute_push_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        self.__target_branch = self.__source_branch = OrchestratorBase.normalize_branch_name(
            GithubOrchestrator.__push_target_branch_query.find(self.__json)[0].value)
        self.__target_hash = self.__source_hash = GithubOrchestrator.__push_target_hash_query.find(self.__json)[0].value
        
        return await OrchestratorBase._execute_push_scan_workflow(self, cxone_service, scm_service, workflow_service)


    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        page_max = 1

        # TODO: need a pager
        # default branch is a protected branch, but they have rules.
        # use default branch if there are no protected branches.


        # this would list all protected branches

        foo = await scm_service.exec("GET", f"/repos/{self._repo_organization}/{self._repo_project_key}/branches", 
                               query = {"protected" : True, "per_page" : page_max},
                               event_msg=self.__json)


        raise NotImplementedError("_get_protected_branches")


    @property
    def _repo_project_key(self) -> str:
        return GithubOrchestrator.__push_project_key_query.find(self.__json)[0].value

    @property
    def _repo_organization(self) -> str:
        return GithubOrchestrator.__push_org_key_query.find(self.__json)[0].value

    @property
    def _repo_slug(self) -> str:
        return self._repo_project_key

    @property
    def _repo_name(self) -> str:
        return self._repo_project_key

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]

    __workflow_map = {
        "installation" : __log_app_install,
        "installation_repositories" : __log_app_install,
        "push" : _execute_push_scan_workflow
    }

    __route_url_parser_dispatch_map = {
        "installation" : __installation_route_urls,
        "installation_repositories" : __installation_route_urls,
        "push" : __push_route_urls
    }

    __clone_url_parser_dispatch_map = {
        "push" : __push_clone_urls
    }
