import zipfile, tempfile, logging
from pathlib import Path, PurePath
from time import perf_counter_ns
from _version import __version__
from .exceptions import OrchestrationException
from cxone_service import CxOneService
from cxone_api.scanning import ScanInspector
from scm_services import SCMService, Cloner
from workflows.state_service import WorkflowStateService
from workflows.messaging import PRDetails

class OrchestratorBase:

    @staticmethod
    def normalize_branch_name(branch):
        return branch.split("/")[-1:].pop()

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(self, headers, webhook_payload):
        self.__webhook_payload = webhook_payload
        self.__headers = headers

    @property
    def config_key(self):
        raise NotImplementedError("config_key")

    @property
    def _headers(self) -> dict:
        return self.__headers

    @property
    def route_urls(self) -> list:
        raise NotImplementedError("route_urls")

    @property
    def _webhook_payload(self) -> str:
        return self.__webhook_payload
    
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
            return self.__headers[key]
        except:
            return None

    async def execute(self, cxone_service: CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        raise NotImplementedError("execute")
    
    async def __exec_scan(self, cxone_service : CxOneService, scm_service : SCMService, tags) -> ScanInspector:
        protected_branches = await self._get_protected_branches(scm_service)

        target_branch, target_hash = await self._get_target_branch_and_hash()
        source_branch, source_hash = await self._get_source_branch_and_hash()
        clone_url = self._repo_clone_url(scm_service.cloner)

        cxone_project_name = await self.get_cxone_project_name()

        if clone_url is None:
            raise OrchestrationException("Clone URL could not be determined.")

        if target_branch in protected_branches:
            check = perf_counter_ns()
            
            OrchestratorBase.log().debug("Starting clone...")
            async with scm_service.cloner.clone(clone_url) as clone_worker:
                code_path = await clone_worker.loc()

                await scm_service.cloner.reset_head(code_path, source_hash)

                OrchestratorBase.log().info(f"{clone_url} cloned in {perf_counter_ns() - check}ns")
                check = perf_counter_ns()

                with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
                    with zipfile.ZipFile(zip_file, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as upload_payload:
                        zip_entries = OrchestratorBase.__get_path_dict(code_path)

                        OrchestratorBase.log().debug(f"[{clone_url}][{source_branch}][{source_hash}] zipping for scan: {zip_entries}")

                        for entry_key in zip_entries.keys():
                            upload_payload.write(entry_key, zip_entries[entry_key])
                        
                        OrchestratorBase.log().info(f"{clone_url} zipped in {perf_counter_ns() - check}ns")
                        

                    try:
                        scan_submit = await cxone_service.execute_scan(zip_file.name, cxone_project_name, \
                                                                        source_branch, clone_url, tags)

                        OrchestratorBase.log().debug(scan_submit)
                        OrchestratorBase.log().info(f"Scan id {scan_submit['id']} created for {clone_url}|{source_branch}|{source_hash}")

                        return ScanInspector(scan_submit)
                    except Exception as ex:
                        OrchestratorBase.log().error(f"{clone_url}:{source_branch}@{source_hash}: No scan created due to exception: {ex}")
                        OrchestratorBase.log().exception(ex)
        else:
            OrchestratorBase.log().info(f"{clone_url}:{source_hash}:{source_branch} is not related to any protected branch: {protected_branches}")


    async def _execute_push_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        OrchestratorBase.log().debug("_execute_push_scan_workflow")
        
        _, hash = await self._get_source_branch_and_hash()

        scan_tags = {
            CxOneService.COMMIT_TAG : hash,
            "workflow" : "push",
            "cxone-flow" : __version__,
            "service" : cxone_service.moniker
        }

        return await self.__exec_scan(cxone_service, scm_service, scan_tags)



    async def _execute_pr_scan_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService) -> ScanInspector:
        OrchestratorBase.log().debug("_execute_pr_scan_workflow")

        source_branch, source_hash = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        scan_tags = {
            CxOneService.COMMIT_TAG : source_hash,
            CxOneService.PR_ID_TAG : self._pr_id,
            CxOneService.PR_TARGET_TAG : target_branch,
            CxOneService.PR_STATUS_TAG : self._pr_status,
            CxOneService.PR_STATE_TAG : self._pr_state,
            "workflow" : "pull-request",
            "cxone-flow" : __version__,
            "service" : cxone_service.moniker
        }

        inspector = await self.__exec_scan(cxone_service, scm_service, scan_tags)
        await workflow_service.start_pr_scan_workflow(inspector.project_id, inspector.scan_id, 
                                                      PRDetails(clone_url=self._repo_clone_url(scm_service.cloner), 
                                                      repo_project=self._repo_project_key, repo_slug=self._repo_slug, 
                                                      organization=self._repo_organization, pr_id=self._pr_id,
                                                      source_branch=source_branch, target_branch=target_branch))
        return inspector

    async def _execute_pr_tag_update_workflow(self, cxone_service : CxOneService, scm_service : SCMService, workflow_service : WorkflowStateService):
        _, source_hash = await self._get_source_branch_and_hash()
        target_branch, _ = await self._get_target_branch_and_hash()

        updated_scans = await cxone_service.update_scan_pr_tags(await self.get_cxone_project_name(), self._pr_id, source_hash,
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
    


