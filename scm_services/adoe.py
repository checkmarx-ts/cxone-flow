import json
from .scm import SCMService
from cxone_api.util import json_on_ok
from typing import Union, Dict
from datetime import datetime, UTC
import markdown as md


class ADOEService(SCMService):

    __thread_prop_key = "cxoneflow"

    @staticmethod
    def __create_thread_props(scanid : str) -> dict:
        return json.dumps({
            "timestamp" : datetime.now(UTC).isoformat(),
            "scanid" : scanid
        })


    async def __get_pr_thread(self, organization : str, project : str, repo_slug : str, pr_number : str) -> Union[None, Dict]:
    
        threads = json_on_ok(await self.exec("GET", path = f"{organization}/{project}/_apis/git/repositories/{repo_slug}/pullRequests/{pr_number}/threads", 
                                             query = {"api-version": "7.0"}))

        for thread in threads['value']:
            if 'properties' in thread.keys() and thread['properties'] is not None and ADOEService.__thread_prop_key in thread['properties'].keys() \
                and not bool(thread['isDeleted']):
                return thread['id']

        return None

    async def __update_pr_thread(self, organization : str, project : str, repo_slug : str, pr_number : str, thread_id : str, annotation : str) -> Union[None, Dict]:
        payload = {
            "content" : annotation
        }
        
        thread = json_on_ok(await self.exec("PATCH", 
                                            path=f"{organization}/{project}/_apis/git/repositories/{repo_slug}/pullRequests/{pr_number}/threads/{thread_id}/comments/1",
                                            query = {"api-version": "7.0"}, body=json.dumps(payload), extra_headers={"Content-Type" : "application/json"}))
        
        if thread is None:
            ADOEService.log().error(f"Unable to update PR thread {thread_id}.")
        else:
            ADOEService.log().debug(f"PR thread {thread_id} updated on PR {pr_number}")
    

    async def __create_pr_thread(self, organization : str, project : str, repo_slug : str, pr_number : str, annotation : str, scanid : str):
        payload = {
            "comments" : [
                {
                    "parentCommentId" : 0,
                    "content" : annotation,
                    "commentType" : 1
                }
            ],
            "status" : 1,
            "properties" : {
              ADOEService.__thread_prop_key : ADOEService.__create_thread_props(scanid)
            }
        }

        thread = json_on_ok(await self.exec("POST", path=f"{organization}/{project}/_apis/git/repositories/{repo_slug}/pullRequests/{pr_number}/threads",
                                            query = {"api-version": "7.0"}, body=json.dumps(payload), extra_headers={"Content-Type" : "application/json"}))
        
        if thread is None:
            ADOEService.log().error(f"Unable to create PR thread for scan id {scanid}")
        else:
            ADOEService.log().debug(f"PR thread {thread['id']} created on PR {pr_number} for scan id {scanid}")

        



    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, 
                               scanid : str, markdown : str):
        existing_thread = await self.__get_pr_thread(organization, project, repo_slug, pr_number)

        content = md.markdown(markdown, extensions=['tables'])

        if existing_thread is None:
            await self.__create_pr_thread(organization, project, repo_slug, pr_number, content, scanid)
        else:
            await self.__update_pr_thread(organization, project, repo_slug, pr_number, existing_thread, content)


    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return self._form_url(f"{organization}/{project}/_git/{repo_slug}", path=code_path, version=f"GB{branch}", 
                              line=code_line, lineEnd=code_line, lineStartColumn=0, lineEndColumn=1024, lineStyle="plain", _a="contents")
