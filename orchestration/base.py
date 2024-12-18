import zipfile, tempfile, logging
from pathlib import Path, PurePath
from time import perf_counter_ns
from _version import __version__
from .exceptions import OrchestrationException
from cxone_api.high.scans import ScanInspector
from scm_services import SCMService
from cxone_service import CxOneService
from scm_services.cloner import Cloner, CloneWorker, CloneAuthException
from workflows.exceptions import WorkflowException
from workflows.messaging import PRDetails
from workflows.utils import AdditionalScanContentWriter
from workflows import ScanWorkflow
from api_utils.auth_factories import EventContext
from enum import Enum
from typing import Tuple, List, Dict
from services import CxOneFlowServices
from cxone_api.high.projects import ProjectRepoConfig


class OrchestratorBase:
    
    class ScanAction(Enum):
        DEFERRED = "deferred"
        EXECUTING = "executing"
        SKIPPED = "skipped"


    @staticmethod
    def normalize_branch_name(branch):
        return branch.split("/")[-1:].pop()

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(self, event_context : EventContext):
        self.__event_context = event_context
        self.__isdeferred = False

    @property
    def deferred_scan(self):
        return self.__isdeferred

    @deferred_scan.setter
    def deferred_scan(self, value):
        self.__isdeferred = value

    @property
    def config_key(self):
        raise NotImplementedError("config_key")

    @property
    def event_context(self) -> EventContext:
        return self.__event_context
    
    @property
    def event_name(self) -> str:
        raise NotImplementedError("route_urls")


    @property
    def route_urls(self) -> list:
        raise NotImplementedError("route_urls")
    
    @staticmethod
    def __get_path_dict(path : str, root : str = None) -> dict:
        return_dict = {}

        use_root = path if root is None else root

        p = Path(path)

        for entry in p.iterdir():
            if entry.is_dir():
                return_dict |= OrchestratorBase.__get_path_dict(entry, use_root)
            else:
                return_dict[entry] = PurePath(entry).relative_to(use_root)
        return return_dict
    
    def get_header_key_safe(self, key):
        try:
            return self.event_context.headers[key]
        except:
            return None

    async def execute(self, services : CxOneFlowServices):
        raise NotImplementedError("execute")

    async def execute_deferred(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter],
                               scan_tags : Dict[str,str]):
        raise NotImplementedError("execute_deferred")
    
    async def _get_clone_worker(self, scm_service : SCMService, clone_url : str, failures : int) -> CloneWorker:
        return await scm_service.cloner.clone(clone_url)
    
    async def __exec_immediate_scan(self, cxone_service : CxOneService, scm_service : SCMService, 
        clone_url : str, source_hash : str, source_branch : str, 
        project_config : ProjectRepoConfig, tags : dict, 
        additional_content : List[AdditionalScanContentWriter]) -> Tuple[ScanInspector, ScanAction]:
        check = perf_counter_ns()
        
        OrchestratorBase.log().debug("Starting clone...")
        # Do 1 clone retry if there is an auth failure.
        clone_auth_fails = 0
        while clone_auth_fails <= 1:
            try:
                async with await self._get_clone_worker(scm_service, clone_url, clone_auth_fails) as clone_worker:
                    code_path = await clone_worker.loc()

                    await scm_service.cloner.reset_head(code_path, source_hash)

                    OrchestratorBase.log().info(f"{clone_url} cloned in {perf_counter_ns() - check}ns")

                    if additional_content is not None and len(additional_content) > 0:
                        check = perf_counter_ns()
                        for ac in additional_content:
                            written = await ac.write_content(code_path)
                            OrchestratorBase.log().debug(f"Wrote additional content: {written}")
                        OrchestratorBase.log().info(f"Additional content created in {perf_counter_ns() - check}ns")

                    check = perf_counter_ns()

                    with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
                        with zipfile.ZipFile(zip_file, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as upload_payload:
                            zip_entries = OrchestratorBase.__get_path_dict(code_path)

                            OrchestratorBase.log().debug(f"[{clone_url}][{source_branch}][{source_hash}] zipped {len(zip_entries)} files for scan.")

                            for entry_key in zip_entries.keys():
                                upload_payload.write(entry_key, zip_entries[entry_key])
                            
                            OrchestratorBase.log().info(f"{clone_url} zipped in {perf_counter_ns() - check}ns")


                        try:
                            scan_submit = await cxone_service.execute_scan(zip_file.name, project_config, \
                                                                            source_branch, clone_url, tags)

                            OrchestratorBase.log().debug(scan_submit)
                            OrchestratorBase.log().info(f"Scan id {scan_submit['id']} created for {clone_url}|{source_branch}|{source_hash}")

                            return ScanInspector(scan_submit), OrchestratorBase.ScanAction.EXECUTING
                        except Exception as ex:
                            OrchestratorBase.log().error(f"{clone_url}:{source_branch}@{source_hash}: No scan created due to exception: {ex}")
                            OrchestratorBase.log().exception(ex)
                            break
            except CloneAuthException as cax:
                if clone_auth_fails <= 1:
                    clone_auth_fails += 1
                    OrchestratorBase.log().exception(cax)
                else:
                    raise


    
    async def __orchestrate_scan(self, services : CxOneFlowServices, scan_tags : dict, workflow : ScanWorkflow, 
                                 additional_content : List[AdditionalScanContentWriter]) -> Tuple[ScanInspector, ScanAction]:
        protected_branches = await self._get_protected_branches(services.scm)

        target_branch, target_hash = await self._get_target_branch_and_hash()
        source_branch, source_hash = await self._get_source_branch_and_hash()
        clone_url = self._repo_clone_url(services.scm.cloner)

        if clone_url is None:
            raise OrchestrationException("Clone URL could not be determined.")

        if target_branch in protected_branches:
            project_config = await services.cxone.load_project_config(await self.get_cxone_project_name())

            if not self.deferred_scan and not services.resolver.skip and await services.cxone.sca_selected(project_config, source_branch):
                try:
                    resolver_tag = await services.cxone.get_resolver_tag_for_project(project_config, 
                                                                                    services.resolver.project_tag_key, services.resolver.default_tag)
                    if resolver_tag is not None:
                        if await services.resolver.request_resolver_scan(resolver_tag, project_config, services.scm.cloner, clone_url, source_hash, 
                                                                         workflow, self.__event_context, f"{self.__class__.__module__}.{self.__class__.__name__}"):
                            return None, OrchestratorBase.ScanAction.DEFERRED
                        else:
                            OrchestratorBase.log().warning(f"Resolver scan request failed for tag {resolver_tag}, proceeding with scanning via other engines.")

                except WorkflowException as ex:
                    OrchestratorBase.log().exception("Resolver workflow exception, SCA scan will run resolver server-side.", ex)

            return await self.__exec_immediate_scan(services.cxone, services.scm, clone_url, source_hash, 
                                            source_branch, project_config, scan_tags, additional_content)
        else:
            OrchestratorBase.log().info(f"{clone_url}:{source_hash}:{source_branch} is not related to any protected branch: {protected_branches}")
            return None, OrchestratorBase.ScanAction.SKIPPED

    async def _execute_push_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                          scan_tags : Dict[str, str]=None) -> ScanAction:
        OrchestratorBase.log().debug("_execute_push_scan_workflow")
        
        _, hash = await self._get_source_branch_and_hash()

        submitted_scan_tags = {
            CxOneService.COMMIT_TAG : hash,
            "workflow" : str(ScanWorkflow.PUSH),
            "cxone-flow" : __version__,
            "service" : services.cxone.moniker
        }

        if scan_tags is not None:
            submitted_scan_tags.update(scan_tags)

        _, action = await self.__orchestrate_scan(services, submitted_scan_tags, ScanWorkflow.PUSH, additional_content)

        return action



    async def _execute_pr_scan_workflow(self, services : CxOneFlowServices, additional_content : List[AdditionalScanContentWriter]=None, 
                                        scan_tags : Dict[str, str]=None) -> ScanAction:
        OrchestratorBase.log().debug("_execute_pr_scan_workflow")

        source_branch, source_hash = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        submitted_scan_tags = {
            CxOneService.COMMIT_TAG : source_hash,
            CxOneService.PR_ID_TAG : self._pr_id,
            CxOneService.PR_TARGET_TAG : target_branch,
            CxOneService.PR_STATUS_TAG : self._pr_status,
            CxOneService.PR_STATE_TAG : self._pr_state,
            "workflow" : str(ScanWorkflow.PR),
            "cxone-flow" : __version__,
            "service" : services.cxone.moniker
        }

        if scan_tags is not None:
            submitted_scan_tags.update(scan_tags)

        inspector, scan_action = await self.__orchestrate_scan(services, submitted_scan_tags, ScanWorkflow.PR, additional_content)
        if inspector is not None and scan_action is OrchestratorBase.ScanAction.EXECUTING:
            await services.pr.start_pr_scan_workflow(inspector.project_id, inspector.scan_id, 
                                                        PRDetails.factory(event_context=self.event_context, clone_url=self._repo_clone_url(services.scm.cloner), 
                                                        repo_project=self._repo_project_key, repo_slug=self._repo_slug, 
                                                        organization=self._repo_organization, pr_id=self._pr_id,
                                                        source_branch=source_branch, target_branch=target_branch))
        elif scan_action is OrchestratorBase.ScanAction.DEFERRED:
            OrchestratorBase.log().info(f"PR workflow deferred for PR {self._pr_id}.")
        else:
            OrchestratorBase.log().warning(f"No scan returned, PR workflow not started for PR {self._pr_id}.")

        return scan_action

    async def _execute_pr_tag_update_workflow(self, services : CxOneFlowServices):
        _, source_hash = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        updated_scans = await services.cxone.update_scan_pr_tags(await self.get_cxone_project_name(), self._pr_id, source_hash,
                                                                target_branch, self._pr_state, self._pr_status)

        OrchestratorBase.log().info(f"Updated scan tags for scans: {updated_scans}")
        return updated_scans

    
    async def _get_target_branch_and_hash(self) -> tuple:
        raise NotImplementedError("_get_target_branch_and_hash")

    async def _get_source_branch_and_hash(self) -> tuple:
        raise NotImplementedError("_get_source_branch_and_hash")

    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        raise NotImplementedError("_get_protected_branches")

    async def is_signature_valid(self, shared_secret : str) -> bool:
        raise NotImplementedError("is_signature_valid")
    
    async def get_cxone_project_name(self) -> str:
        raise NotImplementedError("get_cxone_project_name")


    @property
    def _pr_state(self) -> str:
        raise NotImplementedError("_pr_state")

    @property
    def _pr_status(self) -> str:
        raise NotImplementedError("_pr_status")

    @property
    def _pr_id(self) -> str:
        raise NotImplementedError("_pr_id")
    
    @property
    def _repo_project_key(self) -> str:
        raise NotImplementedError("_repo_project_key")

    @property
    def _repo_organization(self) -> str:
        raise NotImplementedError("_repo_organization")

    @property
    def _repo_slug(self) -> str:
        raise NotImplementedError("_repo_slug")

    def _repo_clone_url(self, cloner : Cloner) -> str:
        raise NotImplementedError("_repo_clone_uri")

    @property
    def _repo_name(self) -> str:
        raise NotImplementedError("_repo_name")
    
    @property
    def is_diagnostic(self) -> bool:
        raise NotImplementedError("is_diagnostic")
    


