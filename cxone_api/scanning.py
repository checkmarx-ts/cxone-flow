from jsonpath_ng import parse
from .projects import ProjectRepoConfig
from . import CxOneClient
from .util import json_on_ok
from .exceptions import ScanException
from requests import Response


class ScanInvoker:
    @staticmethod
    async def scan_get_response(cxone_client : CxOneClient, project_repo : ProjectRepoConfig, branch : str, engines : list = None , tags : dict = None, src_zip_path : str = None,
                   clone_user : str = None, clone_cred_type : str = None, clone_cred_value : str = None) -> Response:
        submit_payload = {}

        target_repo = await project_repo.repo_url
       
        if (not await project_repo.is_scm_imported) or (src_zip_path is not None) or (clone_cred_value is not None):
            submit_payload["project"] = {"id" : project_repo.project_id}

            if src_zip_path is not None:
                submit_payload["handler"] = {"uploadUrl" : await ScanInvoker.__upload_zip(cxone_client, src_zip_path)}
                submit_payload["type"] = "upload"
            else:
                submit_payload["type"] = "git"
                submit_payload["handler"] = {}


            submit_payload["handler"]["branch"] = "unknown" if branch is None else branch
            if not clone_cred_value is None and src_zip_path is None:
                submit_payload["handler"]["credentials"] = {
                    "username" : clone_user if clone_user is not None else "",
                    "type" : clone_cred_type,
                    "value" : clone_cred_value
                }


            submit_payload["config"] = [{ "type" : x, "value" : {} } for x in engines] if engines is not None else {}

            if tags is not None:
                submit_payload["tags"] = tags

            if target_repo is not None:
                submit_payload["handler"]["repoUrl"] = target_repo

            return  await cxone_client.execute_scan(submit_payload)
        else:
            submit_payload["repoOrigin"] = await project_repo.scm_type
            submit_payload["project"] = {
                "repoIdentity" : await project_repo.scm_repo_id,
                "repoUrl" : await project_repo.repo_url,
                "projectId" : project_repo.project_id,
                "defaultBranch" : branch,
                "scannerTypes" : engines if engines is not None else [],
                "repoId" : await project_repo.repo_id
            }

            scm_org = await project_repo.scm_org

            return await cxone_client.execute_repo_scan(await project_repo.scm_id, project_repo.project_id, 
                                                                        scm_org if scm_org is not None else "anyorg", submit_payload)

    @staticmethod
    async def scan_get_scanid(cxone_client : CxOneClient, project_repo : ProjectRepoConfig, branch : str, engines : list = None , tags : dict = None, src_zip_path : str = None,
                   clone_user : str = None, clone_cred_type : str = None, clone_cred_value : str = None) -> str:
        
        response = await ScanInvoker.scan_get_response(cxone_client, project_repo, branch, engines, tags, src_zip_path, clone_user, clone_cred_type, clone_cred_value)
        response_json = response.json()

        if not response.ok:
            raise ScanException(f"Scan error for project {project_repo.project_id}: Status: {response.status_code} : {response.json()}")
        
        return json_on_ok(response_json)['id'] if "id" in response_json.keys() else None


    @staticmethod
    async def __upload_zip(cxone_client : CxOneClient, zip_path : str) -> str:
        upload_url = json_on_ok(await cxone_client.get_upload_link())['url']

        upload_response = await cxone_client.upload_to_link(upload_url, zip_path)
        if not upload_response.ok:
            return None

        return upload_url

class ScanInspector:

    __root_status_query = parse("$.status")
    __scan_engines_query = parse("$.engines")
    __status_details_query = parse("$.statusDetails")


    __executing_states = ["Queued", "Running"]
    __failed_states = ["Failed", "Canceled"]
    __maybe_states = ["Partial"]
    __success_states = ["Completed"]

    def __init__(self, json : dict):
        self.__json = json

    def __root_status(self):
        return ScanInspector.__root_status_query.find(self.__json)[0].value
    
    def __requested_engines(self):
        return ScanInspector.__scan_engines_query.find(self.__json)[0].value

    def __status_details(self):
        return ScanInspector.__status_details_query.find(self.__json)[0].value

    def __current_engine_states(self):
        return_states = []
        engines = self.__requested_engines()
        details = self.__status_details()
        for detail_dict in details:
            if detail_dict['name'] in engines:
                if detail_dict['status'] not in return_states:
                    return_states.append(detail_dict['status'])
        
        return return_states


    @property
    def json(self) -> dict:
        return self.__json

    @property
    def executing(self):
        if self.__root_status in ScanInspector.__executing_states:
            return True
        elif self.__root_status in ScanInspector.__maybe_states:
            return len([s for s in self.__current_engine_states() if s in ScanInspector.__executing_states + ScanInspector.__maybe_states]) > 0
        
        return False

    @property
    def failed(self):
        if self.__root_status in ScanInspector.__failed_states:
            return True

        return False

    @property
    def successful(self):
        if self.__root_status in ScanInspector.__success_states:
            return True
        elif self.executing:
            return False
        elif self.__root_status in ScanInspector.__maybe_states:
            maybe = [s for s in self.__current_engine_states() if s in ScanInspector.__maybe_states]
            success = [s for s in self.__current_engine_states() if s in ScanInspector.__success_states]
            return len(maybe) == 0 and len(success) > 0
        
        return False
    
    @property
    def state_msg(self):
        engine_statuses = []

        for detail in self.__status_details():
            stub = f"{detail['name']}: {detail['status']}"
            if detail['status'] not in ScanInspector.__success_states and len(detail['details']) > 0:
                engine_statuses.append(f"{stub}({detail['details']})")
            else:
                engine_statuses.append(stub)

        return f"Status: {self.__root_status()} [{'|'.join(engine_statuses)}]"



class ScanLoader:

    @staticmethod
    async def load(cxone_client : CxOneClient, scanid : str) -> ScanInspector:
        scan = json_on_ok(await cxone_client.get_scan(scanid))
        return ScanInspector(scan)
