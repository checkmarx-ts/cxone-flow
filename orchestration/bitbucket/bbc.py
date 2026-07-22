from jsonpath_ng.ext.parser import parse
from typing import Dict, List
from cxone_api.high.scans import ScanInspector
from orchestration.naming import BitbucketCloudProjectNaming
from cxone_api.util import json_on_ok
from orchestration.exceptions import OrchestrationException
from .bbbase import BitBucketAbstractOrchestrator
from api_utils.auth_factories import EventContext
from services import CxOneFlowServices, SCMService
from .bbc_util import remove_auth_from_url


class BitBucketCloudOrchestrator(BitBucketAbstractOrchestrator):

    __route_urls_query = parse("$.repository.links.html.href")
    __repo_full_name_query = parse("$.repository.full_name")
    __repo_project_name_query = parse("$.repository.project.name")
    __repo_project_key_query = parse("$.repository.project.key")
    __clone_urls_query = parse("$.links.clone[*]")
    __repo_workspace_slug_query = parse("$.repository.workspace.slug")

    __first_push_commit_query = parse("$.push.changes[?(@.new.target.type=='commit')]")

    __branchmodel_name_query = parse("$..['development','production'].branch.name")

    __pr_draft_query = parse("$.pullrequest.draft")
    __pr_self_link_query = parse("$.pullrequest.links.html.href")
    __pr_id_query = parse("$.pullrequest.id")
    __pr_state_query = parse("$.pullrequest.state")
    __pr_source_branch_query = parse("$.pullrequest.source.branch.name")
    __pr_dest_branch_query = parse("$.pullrequest.destination.branch.name")
    __pr_event_short_dest_hash_query = parse("$.pullrequest.destination.commit.hash")
    __pr_event_short_source_hash_query = parse("$.pullrequest.source.commit.hash")
    __pr_participants_query = parse(
        "$.pullrequest.participants[?(@.role == 'REVIEWER')]"
    )

    def __init__(self, event_context: EventContext):
        BitBucketAbstractOrchestrator.__init__(self, event_context)

        self.__clone_urls = {}

        self.__route_urls = [
            url.value
            for url in BitBucketCloudOrchestrator.__route_urls_query.find(
                self.event_context.message
            )
        ]

        if len(self.__route_urls) == 0:
            raise OrchestrationException(
                "Route URLs could not be found in the payload."
            )

    def __is_pr_draft(self) -> bool:
        return bool(
            BitBucketCloudOrchestrator.__pr_draft_query.find(self.event_context.message)
            .pop()
            .value
        )

    @property
    def config_key(self):
        return "bbc"

    @property
    def route_urls(self) -> list:
        return self.__route_urls

    @property
    def is_diagnostic(self) -> bool:
        return False

    def _repo_clone_url(self, cloner) -> str:
        return self.__clone_urls[
            cloner.select_protocol_from_supported(self.__clone_urls.keys())
        ]

    async def _get_target_branch_and_hash(self) -> tuple:
        return self.__target_branch, self.__target_hash

    async def _get_source_branch_and_hash(self) -> tuple:
        return self.__source_branch, self.__source_hash

    async def _get_protected_branches(self, scm_service: SCMService) -> List:
        branchmodel_config = json_on_ok(
            await scm_service.exec(
                "GET",
                f"/repositories/{self._repo_organization}/{self._repo_slug}/effective-branching-model",
            )
        )
        return list(
            set(
                [
                    name.value
                    for name in BitBucketCloudOrchestrator.__branchmodel_name_query.find(
                        branchmodel_config
                    )
                ]
            )
        )

    def __init_clone_urls(self, repo_data: Dict) -> None:
        for clone_entry in BitBucketCloudOrchestrator.__clone_urls_query.find(
            repo_data
        ):
            name = clone_entry.value.get("name")
            if name is not None:
                if name.lower().startswith("http"):
                    # Normalize by removing the auth part since that is provided in the config and reformed
                    # for clone/api requests.
                    self.__clone_urls[name] = remove_auth_from_url(
                        clone_entry.value.get("href")
                    )
                else:
                    self.__clone_urls[name] = clone_entry.value.get("href")

    async def execute(self, services: CxOneFlowServices):
        if self.event_name not in BitBucketCloudOrchestrator.__workflow_map.keys():
            BitBucketCloudOrchestrator.log().error(
                f"Unhandled event type: {self.event_name}"
            )
            return
        else:
            return await BitBucketCloudOrchestrator.__workflow_map[self.event_name](
                self, services
            )

    async def handle_delegated_scan(self, services: CxOneFlowServices, scan_id: str):
        if (
            self.event_name
            not in BitBucketCloudOrchestrator.__delegate_scan_handler_map.keys()
        ):
            BitBucketCloudOrchestrator.log().error(
                f"Unhandled delegated scan event type: {self.event_name}"
            )
            return
        return await BitBucketCloudOrchestrator.__delegate_scan_handler_map[
            self.event_name
        ](self, services, scan_id)

    async def handle_delegated_pr_scan_hard_fail(
        self, services: CxOneFlowServices, fail_msg: str
    ):
        await self.__populate_common_pr_data(services.scm)
        await services.scm.exec_pr_prescan_failure(
            await self._make_prdetails(services), fail_msg
        )

    async def __populate_common_event_data(self, scm_service: SCMService):
        self._repo_project_key = (
            BitBucketCloudOrchestrator.__repo_project_key_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self._repo_project_name = (
            BitBucketCloudOrchestrator.__repo_project_name_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self._repo_name = (
            BitBucketCloudOrchestrator.__repo_full_name_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self._repo_organization = (
            BitBucketCloudOrchestrator.__repo_workspace_slug_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )

        repo_data = json_on_ok(
            await scm_service.exec("GET", f"repositories/{self._repo_name}")
        )
        self._repo_slug = repo_data.get("slug")
        self.__init_clone_urls(repo_data)

    async def __populate_common_push_data(
        self, commit_dict: Dict, scm_service: SCMService
    ):
        await self.__populate_common_event_data(scm_service)

        self.__source_branch = self.__target_branch = None
        self.__source_hash = self.__target_hash = None

        new_commit = commit_dict.get("new")
        self.__source_branch = self.__target_branch = new_commit.get("name")
        self.__source_hash = self.__target_hash = new_commit.get("target").get("hash")

    async def _execute_push_scan_workflow(self, services: CxOneFlowServices):
        found_first_commit = BitBucketCloudOrchestrator.__first_push_commit_query.find(
            self.event_context.message
        )
        if len(found_first_commit) > 0:
            first_commit = found_first_commit.pop().value

            await self.__populate_common_push_data(first_commit, services.scm)
            return await BitBucketAbstractOrchestrator._execute_push_scan_workflow(
                self, services
            )
        else:
            BitBucketCloudOrchestrator.log().info("No commits found to handle.")

    async def _execute_delegated_push_scan_workflow(
        self, services: CxOneFlowServices, scan_id: str
    ):
        found_first_commit = BitBucketCloudOrchestrator.__first_push_commit_query.find(
            self.event_context.message
        )
        if len(found_first_commit) > 0:
            first_commit = found_first_commit.pop().value

            await self.__populate_common_push_data(first_commit, services.scm)
            return await BitBucketAbstractOrchestrator._execute_delegated_push_scan_workflow(
                self, services, scan_id
            )
        else:
            BitBucketCloudOrchestrator.log().info("No commits found to handle.")

    async def __populate_common_pr_data(self, scm_service: SCMService):
        await self.__populate_common_event_data(scm_service)
        self._pr_id = str(
            BitBucketCloudOrchestrator.__pr_id_query.find(self.event_context.message)
            .pop()
            .value
        )
        self._pr_state = (
            BitBucketCloudOrchestrator.__pr_state_query.find(self.event_context.message)
            .pop()
            .value
        )

        self.__source_branch = (
            BitBucketCloudOrchestrator.__pr_source_branch_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self.__target_branch = (
            BitBucketCloudOrchestrator.__pr_dest_branch_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )

        self.__target_hash = (
            BitBucketCloudOrchestrator.__pr_event_short_dest_hash_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self.__source_hash = (
            BitBucketCloudOrchestrator.__pr_event_short_source_hash_query.find(
                self.event_context.message
            )
            .pop()
            .value
        )
        self._pr_status = self.__get_pr_status()

    def __get_pr_status(self) -> str:
        status = "NO_REVIEWERS"

        participants = [
            p.value
            for p in BitBucketCloudOrchestrator.__pr_participants_query.find(
                self.event_context.message
            )
        ]

        if len(participants) > 0:
            status = "AWAITING_REVIEW"

            changes_requested = [
                p
                for p in participants
                if p.get("state") is not None and p.get("state") == "changes_requested"
            ]
            approved = [p for p in participants if p.get("approved", False) is True]

            if len(approved) > 0 and len(changes_requested) == 0:
                return "APPROVED"
            elif len(approved) > 0 and len(changes_requested) > 0:
                return "PARTIAL_APPROVAL"
            elif len(approved) == 0 and len(changes_requested) > 0:
                return "CHANGES_REQUESTED"

        return status

    async def _execute_pr_scan_workflow(
        self, services: CxOneFlowServices
    ) -> ScanInspector:
        if self.__is_pr_draft():
            BitBucketCloudOrchestrator.log().info(
                f"Skipping draft PR {BitBucketCloudOrchestrator.__pr_self_link_query.find(self.event_context.message).pop().value}"
            )
            return

        await self.__populate_common_pr_data(services.scm)

        existing_scans = await services.cxone.find_pr_scans(
            await services.naming.get_project_name(
                await self.get_default_cxone_project_name(), self.event_context
            ),
            self._pr_id,
            self.__source_hash,
        )
        if len(existing_scans) > 0:
            # This is a tag update, not a scan.
            return await self._execute_pr_tag_update_workflow(services)
        else:
            return await BitBucketAbstractOrchestrator._execute_pr_scan_workflow(
                self, services
            )

    async def _execute_delegated_pr_scan_workflow(
        self, services: CxOneFlowServices, scan_id: str
    ):
        await self.__populate_common_pr_data(services.scm)
        return await BitBucketAbstractOrchestrator._execute_delegated_pr_scan_workflow(
            self, services, scan_id
        )

    async def _execute_pr_tag_update_workflow(
        self, services: CxOneFlowServices
    ) -> ScanInspector:
        if self.__is_pr_draft():
            BitBucketCloudOrchestrator.log().info(
                f"Skipping draft PR {BitBucketCloudOrchestrator.__pr_self_link_query.find(self.event_context.message).pop().value}"
            )
            return

        await self.__populate_common_pr_data(services.scm)

        return await BitBucketAbstractOrchestrator._execute_pr_tag_update_workflow(
            self, services
        )

    async def get_default_cxone_project_name(self) -> str:
        return BitbucketCloudProjectNaming.create_project_name(
            self._repo_organization,
            self._repo_project_key,
            self._repo_project_name,
            self._repo_slug,
        )

    __workflow_map = {
        "repo:push": _execute_push_scan_workflow,
        "pullrequest:created": _execute_pr_scan_workflow,
        "pullrequest:updated": _execute_pr_scan_workflow,
        "pullrequest:fulfilled": _execute_pr_tag_update_workflow,
        "pullrequest:rejected": _execute_pr_tag_update_workflow,
        "pullrequest:approved": _execute_pr_tag_update_workflow,
        "pullrequest:unapproved": _execute_pr_tag_update_workflow,
        "pullrequest:changes_request_created": _execute_pr_tag_update_workflow,
        "pullrequest:changes_request_removed": _execute_pr_tag_update_workflow,
    }

    __delegate_scan_handler_map = {
        "repo:push": _execute_delegated_push_scan_workflow,
        "pullrequest:created": _execute_delegated_pr_scan_workflow,
        "pullrequest:updated": _execute_delegated_pr_scan_workflow,
    }
