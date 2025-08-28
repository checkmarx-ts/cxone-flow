import zipfile, tempfile, logging, asyncio
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
from workflows import ScanWorkflow
from api_utils.auth_factories import EventContext
from enum import Enum
from typing import Tuple, List, Dict, Any
from services import CxOneFlowServices
from cxone_api.high.projects import ProjectRepoConfig


class AbstractOrchestrator:
    
    class ScanAction(Enum):
        DELEGATED = "delegated"
        EXECUTING = "executing"
        SKIPPED = "skipped"
        FAILED = "failed"
        COMPLETE = "complete"


    @staticmethod
    def normalize_branch_name(branch):
        return branch.lstrip("/").replace("refs/heads/", "")

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(self, event_context : EventContext):
        self.__event_context = event_context
        self.__isdelegated = False

    @property
    def delegated_scan(self):
        return self.__isdelegated

    @delegated_scan.setter
    def delegated_scan(self, value):
        self.__isdelegated = value

    @property
    def config_key(self):
        raise NotImplementedError("config_key")

    @property
    def event_context(self) -> EventContext:
        return self.__event_context
    
    @property
    def event_name(self) -> str:
        raise NotImplementedError("event_name")


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
                return_dict |= AbstractOrchestrator.__get_path_dict(entry, use_root)
            elif entry.is_file():
                return_dict[entry] = PurePath(entry).relative_to(use_root)
            else:
                AbstractOrchestrator.log().warning(f"File skipped: {str(entry)} (Symlink: {entry.is_symlink()})")
        return return_dict
    
    def get_header_key_safe(self, key):
        try:
            return self.event_context.headers[key]
        except:
            return None

    async def execute(self, services : CxOneFlowServices) -> Any:
        raise NotImplementedError("execute")

    async def handle_delegated_scan(self, services : CxOneFlowServices, scan_id : str):
        raise NotImplementedError("handle_delegated_scan")
    


    @staticmethod
    def __zip_write_delegate(zip_entries : Dict, zipfile : zipfile.ZipFile):
        try:
            for entry_key in zip_entries.keys():
                AbstractOrchestrator.log().debug(f"Writing file [{zip_entries[entry_key]}] @ {zipfile.fp.tell()}")
                zipfile.write(entry_key, zip_entries[entry_key])
        except ValueError as vex:
            AbstractOrchestrator.log().exception("ValueError exception indicating 'write to file that is closed'" +
                                                 " indicates the MQ is timing out waiting for message ACK.  You may need to increase the" + 
                                                 " timeout for consumed message acknowledgements.", vex)
            raise
        except BaseException as ex:
            AbstractOrchestrator.log().exception(ex)
            raise


    @staticmethod
    async def exec_local_scan(code_path : str, cxone_service : CxOneService,
                              scan_source_msg : str, source_branch : str, project_config : ProjectRepoConfig, 
                              tags : dict) -> Tuple[ScanInspector, ScanAction]:

        check = perf_counter_ns()

        with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
            with zipfile.ZipFile(zip_file, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as upload_payload:
                zip_entries = AbstractOrchestrator.__get_path_dict(code_path)

                AbstractOrchestrator.log().debug(f"[{scan_source_msg}] zipping {len(zip_entries)} files for scan.")

                await asyncio.to_thread(AbstractOrchestrator.__zip_write_delegate, zip_entries, upload_payload)
                
                AbstractOrchestrator.log().info(f"[{scan_source_msg}] zipped {len(zip_entries)} file in {perf_counter_ns() - check}ns")

            scan_submit = await cxone_service.execute_scan(zip_file.name, project_config, source_branch, tags)

            AbstractOrchestrator.log().debug(scan_submit)
            AbstractOrchestrator.log().info(f"Scan id {scan_submit['id']} created for [{scan_source_msg}]")

            return ScanInspector(scan_submit), AbstractOrchestrator.ScanAction.EXECUTING

    @staticmethod
    async def exec_clone_scan(cxone_service : CxOneService, scm_service : SCMService, 
        clone_url : str, source_hash : str, source_branch : str, 
        project_config : ProjectRepoConfig, tags : dict, 
        event_context : EventContext) -> Tuple[ScanInspector, ScanAction]:
        check = perf_counter_ns()
        
        AbstractOrchestrator.log().debug("Starting clone...")
        # Do 1 clone retry if there is an auth failure.
        clone_auth_fails = 0
        while clone_auth_fails <= 1:
            try:
                async with await scm_service.cloner.clone(clone_url, event_context, clone_auth_fails > 0) as clone_worker:
                    code_path = await clone_worker.loc()

                    await scm_service.cloner.reset_head(code_path, source_hash)

                    AbstractOrchestrator.log().info(f"{clone_url} cloned in {perf_counter_ns() - check}ns")

                    return await AbstractOrchestrator.exec_local_scan(code_path, cxone_service, 
                                                                      f"{clone_url}|{source_branch}|{source_hash}", 
                                                                      source_branch, project_config, tags)
            except CloneAuthException as cax:
                if clone_auth_fails <= 1:
                    clone_auth_fails += 1
                    AbstractOrchestrator.log().exception(cax)
                else:
                    raise


    
    async def __orchestrate_scan(self, services : CxOneFlowServices, scan_tags : dict, 
        workflow : ScanWorkflow) -> Tuple[ScanInspector, ScanAction]:
        protected_branches = set(await self._get_protected_branches(services.scm))

        target_branch, target_hash = await self._get_target_branch_and_hash()
        source_branch, source_hash = await self._get_source_branch_and_hash()
        clone_url = self._repo_clone_url(services.scm.cloner)

        if clone_url is None:
            raise OrchestrationException("Clone URL could not be determined.")

        if target_branch in protected_branches:
            AbstractOrchestrator.log().info(f"Scan workflow executing for {clone_url}:{source_hash}:{source_branch} -> {target_branch}")

            project_config = await services.cxone.load_project_config(await self.get_default_cxone_project_name(),
                await services.naming.get_project_name(await self.get_default_cxone_project_name(), self.event_context), 
                clone_url)

            if not self.delegated_scan:
                try:
                    resolver_tag = await services.cxone.get_resolver_tag_for_project(project_config, 
                                                                                    services.resolver.project_tag_key, services.resolver.default_tag)
                    if resolver_tag is not None:
                        if await services.resolver.request_resolver_scan(resolver_tag, project_config, services.scm, services.cxone, 
                                                                         clone_url, source_hash, source_branch, scan_tags, workflow, self.__event_context, 
                                                                         f"{self.__class__.__module__}.{self.__class__.__name__}"):
                            return None, AbstractOrchestrator.ScanAction.DELEGATED
                        else:
                            AbstractOrchestrator.log().warning(f"Delegated scan request failed for tag {resolver_tag} but proceeding with scanning.")

                except WorkflowException as ex:
                    # pylint: disable=E1205
                    AbstractOrchestrator.log().exception("Delegated scan workflow exception.", ex)

            return await AbstractOrchestrator.exec_clone_scan(services.cxone, services.scm, clone_url, source_hash,
                                            source_branch, project_config, scan_tags, self.event_context)
        else:
            AbstractOrchestrator.log().info(f"{clone_url}:{source_hash}:{source_branch} is not related to any protected branch: {protected_branches}")
            return None, AbstractOrchestrator.ScanAction.SKIPPED

    async def _execute_delegated_push_scan_workflow(self, services : CxOneFlowServices, scan_id : str) -> Tuple[ScanInspector, ScanAction]:
        
        # Placeholder for eventual delivery of a Sarif feed.

        AbstractOrchestrator.log().debug(f"_execute_delegated_push_scan_workflow")
        inspector =  await services.cxone.load_scan_inspector(scan_id)
        status = AbstractOrchestrator.ScanAction.COMPLETE

        if inspector.executing:
            status = AbstractOrchestrator.ScanAction.EXECUTING
        elif inspector.failed:
            status = AbstractOrchestrator.ScanAction.FAILED

        return inspector, status


    async def _execute_push_scan_workflow(self, services : CxOneFlowServices, 
                                          scan_tags : Dict[str, str]=None) -> Tuple[ScanInspector, ScanAction]:
        AbstractOrchestrator.log().debug("_execute_push_scan_workflow")
        
        _, hash = await self._get_source_branch_and_hash()

        submitted_scan_tags = {
            CxOneService.COMMIT_TAG : hash,
            "workflow" : str(ScanWorkflow.PUSH),
            "cxone-flow" : __version__,
            "service" : services.cxone.moniker
        }

        if scan_tags is not None:
            submitted_scan_tags.update(scan_tags)

        return await self.__orchestrate_scan(services, submitted_scan_tags, ScanWorkflow.PUSH)


    async def __start_pr_workflow(self, services : CxOneFlowServices, inspector : ScanInspector):

        source_branch, _ = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        await services.pr.start_pr_scan_workflow(inspector.project_id, inspector.scan_id, 
                                                    PRDetails.factory(event_context=self.event_context, 
                                                    clone_url=self._repo_clone_url(services.scm.cloner), 
                                                    repo_project=self._repo_project_key, repo_slug=self._repo_slug, 
                                                    organization=self._repo_organization, pr_id=self._pr_id,
                                                    source_branch=source_branch, target_branch=target_branch))

    async def _execute_delegated_pr_scan_workflow(self, services : CxOneFlowServices, scan_id : str) -> ScanAction:
        AbstractOrchestrator.log().debug("_execute_delegated_pr_scan_workflow")
        await self.__start_pr_workflow(services, await services.cxone.load_scan_inspector(scan_id))
        return AbstractOrchestrator.ScanAction.EXECUTING

    async def _execute_pr_scan_workflow(self, services : CxOneFlowServices, scan_tags : Dict[str, str]=None) -> ScanAction:
        AbstractOrchestrator.log().debug("_execute_pr_scan_workflow")

        _, source_hash = await self._get_source_branch_and_hash()
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

        inspector, scan_action = await self.__orchestrate_scan(services, submitted_scan_tags, ScanWorkflow.PR)
        if inspector is not None and scan_action is AbstractOrchestrator.ScanAction.EXECUTING:
            await self.__start_pr_workflow(services, inspector)
        elif scan_action is AbstractOrchestrator.ScanAction.DELEGATED:
            AbstractOrchestrator.log().info(f"PR workflow delegated for PR {self._pr_id}.")
        else:
            AbstractOrchestrator.log().warning(f"No scan returned, PR workflow not started for PR {self._pr_id}.")

        return scan_action

    async def _execute_pr_tag_update_workflow(self, services : CxOneFlowServices):
        _, source_hash = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        updated_scans = await services.cxone.update_scan_pr_tags(await services.naming.get_project_name(
            await self.get_default_cxone_project_name(), self.event_context), self._pr_id, source_hash,
            target_branch, self._pr_state, self._pr_status)

        AbstractOrchestrator.log().info(f"Updated scan tags for scans: {updated_scans}")
        return updated_scans

    
    async def _get_target_branch_and_hash(self) -> tuple:
        raise NotImplementedError("_get_target_branch_and_hash")

    async def _get_source_branch_and_hash(self) -> tuple:
        raise NotImplementedError("_get_source_branch_and_hash")

    async def _get_protected_branches(self, scm_service : SCMService) -> list:
        raise NotImplementedError("_get_protected_branches")

    async def is_signature_valid(self, shared_secret : str) -> bool:
        raise NotImplementedError("is_signature_valid")
    
    async def get_default_cxone_project_name(self) -> str:
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
    


