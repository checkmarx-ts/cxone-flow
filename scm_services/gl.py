from .scm import SCMService
from api_utils.auth_factories import EventContext
from cxone_api.util import json_on_ok
from api_utils import form_url
from workflows.pr import PullRequestAbstractMarkdownComment
import urllib

class GLService(SCMService):
    __max_content_chars = 1000000

    __notes_api_path = "/projects/:id/merge_requests/:merge_request_iid/notes"
    __note_update_api_path = "/projects/:id/merge_requests/:merge_request_iid/notes/:note_id"


    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, 
        summary_markdown : str, event_context : EventContext):

        pr_api_params = {
            "id" : urllib.parse.quote_plus(repo_slug), 
            "merge_request_iid" : str(pr_number)
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
              self.log().info(f"Updating comment {comment['id']} for PR#{pr_number} on {repo_slug}")
        
        posted = json_on_ok(await self.exec(method, note_url, url_vars=pr_api_params, body={
            "body" : full_markdown if len(full_markdown) <= GLService.__max_content_chars else summary_markdown
        }))

        self.log().debug(f"Comment posted on PR#{pr_number} for scan id {scanid}: {posted}")
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{repo_slug}/-/blob/{branch}{code_path}", f"L{code_line}")
