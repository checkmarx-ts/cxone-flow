import zipfile, tempfile, logging
from pathlib import Path, PurePath
from time import perf_counter_ns
from _version import __version__
from .exceptions import OrchestrationException

class OrchestratorBase:


    @staticmethod
    def log():
        return logging.getLogger("OrchestratorBase")

    def __init__(self, headers, webhook_payload):
        self.__webhook_payload = webhook_payload
        self.__headers = headers

    @property
    def _headers(self):
        return self.__headers

    @property
    def route_urls(self):
        raise NotImplementedError("route_urls")

    @property
    def _webhook_payload(self):
        return self.__webhook_payload
    
    @staticmethod
    def __get_path_dict(path, root=None):
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

    async def execute(self, cxone_service, scm_service):
        raise NotImplementedError("execute")
    
    async def _execute_push_scan_workflow(self, cxone_service, scm_service):
        OrchestratorBase.log().debug("_execute_push_scan_workflow")

        protected_branches = await self._get_protected_branches(scm_service)

        commit_branch, commit_hash = await self._get_target_branch_and_hash()
        clone_url = self._repo_clone_url(scm_service.cloner)

        if clone_url is None:
            raise OrchestrationException("Clone URL could not be determined.")

        if commit_branch in protected_branches:
            check = perf_counter_ns()
            
            OrchestratorBase.log().debug("Starting clone...")
            async with scm_service.cloner.clone(clone_url) as clone_worker:
                code_path = await clone_worker.loc()

                await scm_service.cloner.reset_head(code_path, commit_hash)

                OrchestratorBase.log().info(f"{clone_url} clones in {perf_counter_ns() - check}ns")
                check = perf_counter_ns()

                with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
                    with zipfile.ZipFile(zip_file, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as upload_payload:
                        zip_entries = OrchestratorBase.__get_path_dict(code_path)

                        OrchestratorBase.log().debug(f"[{clone_url}][{commit_branch}][{commit_hash}] zipping for scan: {zip_entries}")

                        for entry_key in zip_entries.keys():
                            upload_payload.write(entry_key, zip_entries[entry_key])
                        
                        OrchestratorBase.log().info(f"{clone_url} zipped in {perf_counter_ns() - check}ns")
                        
                    scan_tags = {
                        "commit" : commit_hash,
                        "workflow" : "push-protected-branch",
                        "cxone-flow" : __version__
                    }

                    try:
                        scan_submit = await cxone_service.execute_scan(zip_file.name, await self.get_cxone_project_name(), \
                                                                        commit_branch, clone_url, scan_tags)

                        OrchestratorBase.log().debug(scan_submit)
                        OrchestratorBase.log().info(f"Scan id {scan_submit['id']} created for {clone_url}:{commit_branch}@{commit_hash}")
                    except Exception as ex:
                        OrchestratorBase.log().error(f"{clone_url}:{commit_branch}@{commit_hash}: No scan created due to exception: {ex}")
                        OrchestratorBase.log().exception(ex)

        else:
            OrchestratorBase.log().info(f"{clone_url}:{commit_hash}:{commit_branch} is not in the protected branch list: {protected_branches}")

    async def _execute_pr_scan_workflow(self, cxone_service, scm_service):
        pass
        
    
    async def _get_target_branch_and_hash(self):
        raise NotImplementedError("_get_target_branch_and_hash")

    async def _get_protected_branches(self, scm_service):
        raise NotImplementedError("_get_protected_branches")

    async def is_signature_valid(self, shared_secret):
        raise NotImplementedError("is_signature_valid")
    
    async def get_cxone_project_name(self):
        raise NotImplementedError("get_cxone_project_name")
    
    @property
    def _repo_project_key(self):
        raise NotImplementedError("_repo_project_key")

    @property
    def _repo_slug(self):
        raise NotImplementedError("_repo_slug")

    def _repo_clone_url(self, cloner):
        raise NotImplementedError("_repo_clone_uri")

    @property
    def _repo_name(self):
        raise NotImplementedError("_repo_name")
    
    @property
    def is_diagnostic(self):
        raise NotImplementedError("is_diagnostic")
    


