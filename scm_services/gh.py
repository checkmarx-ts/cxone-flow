from .scm import SCMService
from api_utils.auth_factories import EventContext
from api_utils.pagers import async_api_page_generator
from api_utils import form_url
from requests import Response
from workflows.pr import PullRequestDecoration
from cxone_api.util import json_on_ok
import json

class GHService(SCMService):
    __max_content_chars = 65535
    __api_page_max = 100


    def __comment_data_extractor(self, resp : Response):
        if resp.ok:
            json = resp.json()
            return json, len(json) >= GHService.__api_page_max
        return None

    def __comment_list_args_gen(self, path : str, event_context : EventContext, offset : int):
        return { 
            "method" : "GET",
            "path" : path,
            "query" : {"per_page" : GHService.__api_page_max, "page" : offset + 1},
            "event_context" : event_context
        }

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, 
        summary_markdown : str, event_context : EventContext):

        content = { "body" : full_markdown if len(full_markdown) <= GHService.__max_content_chars else summary_markdown}

        target_id = None

        async for comment in async_api_page_generator(self.exec, self.__comment_data_extractor,
            lambda offset: self.__comment_list_args_gen(f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", event_context, offset)):
            if 'id' in comment.keys() and 'body' in comment.keys():
                comment_id = comment['id']
                if PullRequestDecoration.matches_identifier(comment['body']):
                    target_id = comment_id
                    break

        if target_id is None:
            resp = json_on_ok(await self.exec("POST", f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", 
                                              body=json.dumps(content), event_context = event_context))
            action = "Created"
            target_id = resp['id']
        else:
            resp = json_on_ok(await self.exec("PATCH", f"/repos/{organization}/{repo_slug}/issues/comments/{target_id}", 
                                              body=json.dumps(content), event_context = event_context))
            action = "Updated"
        
        GHService.log().debug(f"{action} comment {target_id} in PR {pr_number}")

   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")

