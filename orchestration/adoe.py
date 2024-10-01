from .base import OrchestratorBase
import base64, urllib, urllib.parse
from jsonpath_ng import parse
from cxone_api.util import CloneUrlParser
from cxone_service import CxOneService
from scm_services import SCMService
from workflows.state_service import WorkflowStateService
from pathlib import Path
from cxone_api.scanning import ScanInspector
from api_utils.auth_factories import EventContext
from cxone_api.util import json_on_ok

class AzureDevOpsEnterpriseOrchestrator(OrchestratorBase):

    __diag_id = "f844ec47-a9db-4511-8281-8b63f4eaf94e"
    __diagid_query = parse("$.resourceContainers.account.id")
    __remoteurl_query = parse("$.resource.repository.remoteUrl")
    __repo_project_key_query = parse("$.resource.repository.project.name")
    __repo_slug_query = parse("$.resource.repository.name")
    __payload_type_query = parse("$.eventType")
    __repository_id_query = parse("$.resource.repository.id")
    __collection_url_query = parse("$.resourceContainers.collection.baseUrl")
    
    __push_default_branch_query = parse("$.resource.repository.defaultBranch")
    __push_target_branch_query = parse("$.resource.refUpdates..name")
    __push_target_hash_query = parse("$.resource.refUpdates..newObjectId")


    __pr_draft_query = parse("$.resource.isDraft")
    __pr_self_link_query = parse("$.resource._links.web.href")    
    __pr_tohash_query = parse("$.resource.lastMergeTargetCommit[commitId]")
    __pr_tobranch_query = parse("$.resource.targetRefName")
    __pr_fromhash_query = parse("$.resource.lastMergeSourceCommit[commitId]")
    __pr_frombranch_query = parse("$.resource.sourceRefName")
    __pr_id_query = parse("$.resource.pullRequestId")
    __pr_reviewer_status_query = parse("$.resource.reviewers[*].vote")
    __pr_state_query = parse("$.resource.status")


    @property
    def config_key(self):
        return "adoe"

    def __init__(self, event_context : EventContext):
        OrchestratorBase.__init__(self, event_context)

        self.__isdiagnostic = AzureDevOpsEnterpriseOrchestrator.__diag_id in [x.value for x in list(AzureDevOpsEnterpriseOrchestrator.__diagid_query.find(self.event_context.message))]
        if self.__isdiagnostic:
            return

        self.__event = [x.value for x in list(self.__payload_type_query.find(self.event_context.message))][0]
        self.__route_urls = [x.value for x in list(self.__remoteurl_query.find(self.event_context.message))]
        self.__remote_url = self.__route_urls[0]
        self.__default_branches = [OrchestratorBase.normalize_branch_name(x.value) for x in list(self.__push_default_branch_query.find(self.event_context.message))]
        self.__repo_key = [x.value for x in list(self.__repo_project_key_query.find(self.event_context.message))][0]
        self.__repo_slug = [x.value for x in list(self.__repo_slug_query.find(self.event_context.message))][0]
        self.__collection_url = [x.value for x in list(self.__collection_url_query.find(self.event_context.message))][0]
        self.__collection = Path(urllib.parse.urlparse(self.__collection_url).path).name


    @property
    def event_name(self) -> str:
        return self.__event

    async def execute(self, cxone_service: CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        # Get clone urls from repo details since ADO doesn't include all clone protocols in the event.
        repo_details = json_on_ok(await scm_service.exec("GET", f"/{self.__collection}/{self.__repo_key}/_apis/git/repositories/{self.__repo_slug}"))
        http_clone_url = urllib.parse.urlparse(self.__remote_url)
        self.__clone_urls = {
            http_clone_url.scheme : self.__remote_url,
            "ssh" : repo_details['sshUrl']
        }
        return await AzureDevOpsEnterpriseOrchestrator.__workflow_map[self.__event](self, cxone_service, scm_service, workflow_service)

    @property
    def is_diagnostic(self):
        return self.__isdiagnostic

    @property
    def route_urls(self):
        return self.__route_urls

    @property
    def _repo_project_key(self):
        return self.__repo_key

    @property
    def _repo_organization(self) -> str:
        return self.__collection

    @property
    def _repo_name(self):
        return self.__repo_slug

    @property
    def _repo_slug(self):
        return self.__repo_slug

    async def is_signature_valid(self, shared_secret):
        auth = self.get_header_key_safe('Authorization')
        if auth is None:
            AzureDevOpsEnterpriseOrchestrator.log().warning("Authorization header is missing in request, rejecting.")
            return False

        base64_payload = auth.split(" ")[-1:].pop()
        if base64_payload is None:
            AzureDevOpsEnterpriseOrchestrator.log().warning("Authorization header is not in the correct form, rejecting.")
            return False

        sent_secret = base64.b64decode(base64_payload).decode("utf-8").split(":")[-1:].pop()
        return sent_secret == shared_secret

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[cloner.select_protocol_from_supported(self.__clone_urls.keys())]

    # def _repo_clone_url(self, cloner):
    #     parsed_clone_url = urllib.parse.urlparse(self.__remote_url)

    #     if parsed_clone_url.scheme in cloner.supported_protocols:
    #         return self.__remote_url

    #     protocol = cloner.supported_protocols[0]
    #     port = cloner.destination_port

    #     return urllib.parse.urlunparse((protocol, f"{parsed_clone_url.netloc}{f":{port}" if port is not None else ""}", 
    #                                    parsed_clone_url.path, parsed_clone_url.params, parsed_clone_url.query, parsed_clone_url.fragment))
    
    async def _get_protected_branches(self, scm_service : SCMService):
        return self.__default_branches

    async def _get_target_branch_and_hash(self):
        return self.__target_branch, self.__target_hash
    
    async def _get_source_branch_and_hash(self) -> tuple:
        return self.__source_branch, self.__source_hash

    async def get_cxone_project_name(self) -> str:
        p = CloneUrlParser("azure", self.__remote_url)
        return f"{p.org}/{self._repo_project_key}/{self._repo_name}"

    async def __is_pr_draft(self) -> bool:
        return bool(AzureDevOpsEnterpriseOrchestrator.__pr_draft_query.find(self.event_context.message)[0].value)


    async def _execute_push_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        self.__source_branch = self.__target_branch = OrchestratorBase.normalize_branch_name(
            [x.value for x in list(self.__push_target_branch_query.find(self.event_context.message))][0])
        self.__source_hash = self.__target_hash = [x.value for x in list(self.__push_target_hash_query.find(self.event_context.message))][0]

        return await OrchestratorBase._execute_push_scan_workflow(self, cxone_service, scm_service, workflow_service)

    async def _execute_pr_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService) -> ScanInspector:
        if await self.__is_pr_draft():
            AzureDevOpsEnterpriseOrchestrator.log().info(f"Skipping draft PR {AzureDevOpsEnterpriseOrchestrator.__pr_self_link_query.find(self.event_context.message)[0].value}")
            return

        self.__source_branch = OrchestratorBase.normalize_branch_name([x.value for x in list(self.__pr_frombranch_query.find(self.event_context.message))][0])
        self.__target_branch = OrchestratorBase.normalize_branch_name([x.value for x in list(self.__pr_tobranch_query.find(self.event_context.message))][0])
        self.__source_hash = [x.value for x in list(self.__pr_fromhash_query.find(self.event_context.message))][0]
        self.__target_hash = [x.value for x in list(self.__pr_tohash_query.find(self.event_context.message))][0]
        self.__pr_id = str([x.value for x in list(self.__pr_id_query.find(self.event_context.message))][0])

        statuses = list(set([AzureDevOpsEnterpriseOrchestrator.__pr_status_map[x.value] for x in AzureDevOpsEnterpriseOrchestrator.__pr_reviewer_status_query.find(self.event_context.message)]))

        if not len(statuses) > 0:
            self.__pr_status = "NO_REVIEWERS"
        else:
            self.__pr_status = "/".join(statuses)

        self.__pr_state = AzureDevOpsEnterpriseOrchestrator.__pr_state_query.find(self.event_context.message)[0].value

        existing_scans = await cxone_service.find_pr_scans(await self.get_cxone_project_name(), self.__pr_id, self.__source_hash)

        if len(existing_scans) > 0:
            # This is a scan tag update, not a scan.
            return await OrchestratorBase._execute_pr_tag_update_workflow(self, cxone_service, scm_service, workflow_service)
        else:
            repo_details = await scm_service.exec("GET", f"{self.__collection}/{self._repo_project_key}/_apis/git/repositories/{self.__repository_id}")

            if not repo_details.ok:
                AzureDevOpsEnterpriseOrchestrator.log().error(f"Response [{repo_details.status_code}] to request for repository details, event handling aborted.")
                return

            self.__default_branches = [OrchestratorBase.normalize_branch_name(repo_details.json()['defaultBranch'])]
            
            return await OrchestratorBase._execute_pr_scan_workflow(self, cxone_service, scm_service, workflow_service)


    
    @property
    def __repository_id(self) -> str:
        return [x.value for x in list(self.__repository_id_query.find(self.event_context.message))][0]


    @property
    def _pr_id(self) -> str:
        return self.__pr_id

    @property
    def _pr_status(self) -> str:
        return self.__pr_status

    @property
    def _pr_state(self) -> str:
        return self.__pr_state


    __pr_status_map = {
        -10 : "REJECTED",
        -5 : "WAIT_AUTHOR",
        0 : "NO_REVIEW",
        5 : "APPROVED_COMMENTS",
        10 : "APPROVED"
    }

    __workflow_map = {
        "git.push" : _execute_push_scan_workflow,
        "git.pullrequest.created" : _execute_pr_scan_workflow,
        "git.pullrequest.updated" : _execute_pr_scan_workflow
    }
