from .scm import SCMService
from api_utils.auth_factories import EventContext
from api_utils.pagers import async_api_page_generator
from api_utils import form_url
from requests import Response
from workflows.pr_content import PullRequestAbstractMarkdownComment
from workflows.messaging import PRDetails
from cxone_api.util import json_on_ok
from workflows.pr_content import PullRequestCommentContent
import json


class AbstractGHService(SCMService):
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")


class GHServiceNoPRBlock(AbstractGHService):
    __max_content_chars = 65535
    __api_page_max = 100


    def __comment_data_extractor(self, resp : Response):
        if resp.ok:
            json = resp.json()
            return json, len(json) >= GHServiceNoPRBlock.__api_page_max
        return None

    def __comment_list_args_gen(self, path : str, event_context : EventContext, offset : int):
        return { 
            "method" : "GET",
            "path" : path,
            "query" : {"per_page" : GHServiceNoPRBlock.__api_page_max, "page" : offset + 1},
            "event_context" : event_context
        }

    async def __create_or_update_pr_comment(self, organization : str, repo_slug : str, pr_number : str, content : str, 
        event_context : EventContext):

        content = { "body" : content}

        target_id = None

        async for comment in async_api_page_generator(self.exec, self.__comment_data_extractor,
            lambda offset: self.__comment_list_args_gen(f"/repos/{organization}/{repo_slug}/issues/{pr_number}/comments", event_context, offset)):
            if 'id' in comment.keys() and 'body' in comment.keys():
                comment_id = comment['id']
                if PullRequestAbstractMarkdownComment.comment_matches_identifier(comment['body']):
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
        
        GHServiceNoPRBlock.log().debug(f"{action} comment {target_id} in PR {pr_number}")


    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, 
                                                 content.get_content(self.__max_content_chars), pr_details.event_context)
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        return await self.exec_pr_scan_update_decorate(pr_details, content)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        return await self.exec_pr_scan_update_decorate(pr_details, content)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        return await self.exec_pr_scan_update_decorate(pr_details, content)
    




