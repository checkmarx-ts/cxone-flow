from _agent import __agent__
from _version import __version__
from cxone_api.scanning import ScanInvoker, ScanInspector, ScanLoader, ScanFilterConfig
from cxone_api.projects import ProjectRepoConfig
from cxone_api import paged_api
import logging,asyncio
from datetime import datetime

class CxOneException(Exception):
    pass

class CxOneService:

    COMMIT_TAG = "commit"
    PR_ID_TAG = "pr-id"
    PR_TARGET_TAG = "pr-target"
    PR_STATUS_TAG = "pr-status"
    PR_STATE_TAG = "pr-state"

    UPDATABLE_SCANS_STATUSES = ["Completed", "Failed", "Partial"]

    __report_poll_delay_seconds = 30
    __report_generate_timeout_seconds = 600


    @staticmethod
    def log():
        return logging.getLogger("CxOneService")

    __minimum_engine_selection = ['sast']

    def __init__(self, moniker, cxone_client, default_engines, default_scan_tags, default_project_tags):
        self.__client = cxone_client
        self.__moniker = moniker
        self.__default_project_tags = default_project_tags if default_project_tags is not None else {}
        self.__default_scan_tags = default_scan_tags if default_scan_tags is not None else {}
        self.__default_engine_config = default_engines
    
    @property
    def moniker(self):
        return self.__moniker
    
    @property
    def display_link(self):
        return self.__client.display_endpoint
    
    @staticmethod
    def __get_json_or_fail(response):
        if not response.ok:
            raise CxOneException(f"Method: {response.request.method} Url: {response.request.url} Status: {response.status_code} Body: {response.text}")
        else:
            return response.json()

    @staticmethod
    def __succeed_or_throw(response):
        if not response.ok:
            raise CxOneException(f"Method: {response.request.method} Url: {response.request.url} Status: {response.status_code}")
        else:
            return response

    async def update_scan_pr_tags(self, by_project_name : str, by_pr_id : str, by_commit_hash : str, new_target_branch : str, new_state : str, new_status : str) -> list:
        scans_updated = []

        async for scan in paged_api(self.__client.get_scans, "scans", statuses=CxOneService.UPDATABLE_SCANS_STATUSES,
                                    project_names=by_project_name, tags_keys = CxOneService.COMMIT_TAG, tags_values=by_commit_hash):

            # Qualify the PR identifier before updating since the search lacks the ability to filter by AND
            if CxOneService.PR_ID_TAG in scan['tags'] and str(scan['tags'][CxOneService.PR_ID_TAG]) == by_pr_id:
                updated = dict(scan['tags'])
                updated[CxOneService.PR_TARGET_TAG] = new_target_branch
                updated[CxOneService.PR_STATE_TAG] = new_state
                updated[CxOneService.PR_STATUS_TAG] = new_status

                update_response = await self.__client.update_scan_tags(scan['id'], {"tags" : updated})

                if update_response.ok:
                    scans_updated.append(scan['id'])
                else:
                    CxOneService.log().debug(scan)
                    CxOneService.log().warn(f"Unable to update tags for scan id {scan['id']}: Response was {update_response.status_code}:{update_response.text}")

        return scans_updated
    
    def __create_engine_config_dict(self, project_config : dict):
        pass


    async def execute_scan(self, zip_path : str, project_name : str, commit_branch : str, repo_url : str, scan_tags : dict ={}):

        projects_response = CxOneService.__get_json_or_fail (await self.__client.get_projects(name=project_name))

        if int(projects_response['filteredTotalCount']) == 0:
            project_json = CxOneService.__get_json_or_fail (await self.__client.create_project( \
                name=project_name, origin=__agent__, tags=self.__default_project_tags | {"cxone-flow" : __version__, "service" : self.moniker}))
            project_id = project_json['id']
        else:
            project_json = projects_response['projects'][0]
            project_id = project_json['id']

            new_tags = {k:self.__default_project_tags[k] \
                                     for k in self.__default_project_tags.keys() if k not in project_json['tags'].keys()}
            
            # Update the service moniker if it has changed or does not exist.
            if "service" in project_json['tags'].keys():
                if not project_json['tags']['service'] == self.moniker:
                    new_tags['service'] = self.moniker
            else:
                new_tags['service'] = self.moniker

            if len(new_tags.keys()) > 0:
                project_json['tags'] = new_tags | project_json['tags']
                CxOneService.__succeed_or_throw(await self.__client.update_project(project_id, project_json))

        project_config = await ProjectRepoConfig.from_project_json(self.__client, project_json)

        scan__filter_cfg = await ScanFilterConfig.from_project_id(self.__client, project_id)
        engine_config = scan__filter_cfg.compute_filters_with_defaults(self.__default_engine_config)

        if engine_config is None:
            engine_config = await project_config.get_enabled_scanners(commit_branch)

        if len(engine_config) == 0:
            engine_config = CxOneService.__minimum_engine_selection

        return CxOneService.__get_json_or_fail(await ScanInvoker.scan_get_response(self.__client, 
                project_config, commit_branch, engine_config, scan_tags | self.__default_scan_tags, zip_path))


    async def find_pr_scans(self, by_project_name : str, by_pr_id : str, by_commit_hash : str) -> list:
        found_scans = []

        async for scan in paged_api(self.__client.get_scans, "scans", 
                                    project_names=by_project_name, tags_keys = CxOneService.COMMIT_TAG, tags_values=by_commit_hash):
            if CxOneService.PR_ID_TAG in scan['tags'] and str(scan['tags'][CxOneService.PR_ID_TAG]) == by_pr_id:
                found_scans.append(scan['id'])

        return found_scans
    
    async def load_scan_inspector(self, scanid : str) -> ScanInspector:
        return await ScanLoader.load(self.__client, scanid)
    
    async def retrieve_report(self, projectid : str, scanid : str) -> dict:

        create_payload = {
            "reportName" : "improved-scan-report",
            "fileFormat" : "json",
            "reportType" : "cli",
            "data" : {
                "scanId" : scanid,
                "projectId" : projectid
            }
        }

        report_response = CxOneService.__get_json_or_fail(await self.__client.create_report(**create_payload))

        if not 'reportId' in report_response.keys():
            raise CxOneException(f"Malformed response creating a report for scan id {scanid} in project {projectid}")
        else:
            reportid = report_response['reportId']
            CxOneService.log().debug(f"Report Id {reportid} created for scan id {scanid}")

            wait_start = datetime.now()

            while await asyncio.sleep(CxOneService.__report_poll_delay_seconds, 
                                      (datetime.now() - wait_start).total_seconds() < CxOneService.__report_generate_timeout_seconds):
                
                gen_status = CxOneService.__get_json_or_fail(await self.__client.get_report_generation_status(reportid, returnUrl=False))

                if not 'status' in gen_status.keys():
                    raise CxOneException(f"Malformed response obtaining report generation status for report id {reportid}")
                else:
                    if 'completed' == gen_status['status']:
                        return CxOneService.__get_json_or_fail(await self.__client.download_report(reportid))
