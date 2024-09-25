from .scm import SCMService
from api_utils.auth_factories import EventContext
import json
from api_utils import form_url

class GHService(SCMService):
    __max_content_chars = 65535

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, 
        summary_markdown : str, event_context : EventContext):

        content = { "body" : full_markdown if len(full_markdown) <= GHService.__max_content_chars else summary_markdown}

        GHService.log().debug(await self.exec("POST", f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", 
                                              body=json.dumps(content), event_context = event_context))
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")

