from .scm import SCMService
from api_utils.auth_factories import EventContext
from cxone_api.util import json_on_ok
from api_utils import form_url
from workflows.pr_content import PullRequestAbstractMarkdownComment
import urllib
from workflows.pr_content import PullRequestCommentContent, PullRequestStatusContent
from workflows.messaging import PRDetails, ScanMessage

class GLService(SCMService):
    __max_content_chars = 1000000

    __notes_api_path = "/projects/:id/merge_requests/:merge_request_iid/notes"
    __note_update_api_path = "/projects/:id/merge_requests/:merge_request_iid/notes/:note_id"

    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details, content)
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details, content)

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details, content)

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent):
        await self.__create_or_update_pr_comment(pr_details, content)
    
    async def __create_or_update_pr_comment(self, pr_details : PRDetails, content : PullRequestCommentContent):
        pr_api_params = {
            "id" : urllib.parse.quote_plus(pr_details.repo_slug), 
            "merge_request_iid" : str(pr_details.pr_id)
            }

        existing_comments = json_on_ok(await self.exec("GET", GLService.__notes_api_path, 
                                            url_vars=pr_api_params))

        method = "POST"
        note_url = GLService.__notes_api_path
        
        for comment in existing_comments:
          if PullRequestAbstractMarkdownComment.comment_matches_identifier(comment['body']):
              method = "PUT"
              note_url = GLService.__note_update_api_path
              pr_api_params['note_id'] = str(comment['id'])
              self.log().info(f"Updating comment {comment['id']} for PR#{pr_details.pr_id} on {pr_details.repo_slug}")


        posted = json_on_ok(await self.exec(method, note_url, url_vars=pr_api_params, body={
            "body" : content.get_content(GLService.__max_content_chars)}))

        self.log().debug(f"Comment posted on PR#{pr_details.pr_id}: {posted}")

   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{repo_slug}/-/blob/{branch}{code_path}", f"L{code_line}")
