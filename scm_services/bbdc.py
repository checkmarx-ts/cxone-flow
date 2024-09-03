from .scm import SCMService
from cxone_api.util import json_on_ok
import json
from workflows.pr import PullRequestDecoration

class BBDCService(SCMService):
    __max_content_chars = 32000

    # comment "threadResolved" must be false to be updated.
    # permittedOperations.editable should also be true
    # text property should be markdown
    #
    # Get PR activity
    # {{BBDC_URL}}/rest/api/latest/projects/P1/repos/simplyvulnerable/pull-requests/1/activities
    # Use start=page, isLastPage to page through activity

    # Add PR comment
    # {{BBDC_URL}}/rest/api/latest/projects/P1/repos/simplyvulnerable/pull-requests/1/comments
    # {
    # "text": "[//]:#comment!!# MARKDOWN!"
    # }

    # Update PR comment
    # {{BBDC_URL}}/rest/api/latest/projects/P1/repos/simplyvulnerable/pull-requests/1/comments/10
    # {
    #     "version": 1,
    #     "text": "Whatever updated again"
    # }


    async def __bbdc_paged_items_gen(self, path):
        offset = 0
        buf = []
        end = False

        while True:
            if len(buf) == 0 and not end:
                json = json_on_ok(await self.exec("GET", path, {"start" : offset}))
                buf = json['values']
                
                if buf is None or len(buf) == 0:
                    return
                elif json['isLastPage']:
                    end = True
                
                offset = offset + 1
            elif len(buf) == 0 and end:
                return

            yield buf.pop()

    async def __add_comment(self, project : str, repo_slug : str, pr_number : str, markdown : str) -> tuple[int, int]:
        resp_json = json_on_ok(await self.exec("POST", f"/rest/api/latest/projects/{project}/repos/{repo_slug}/pull-requests/{pr_number}/comments", 
                        body=json.dumps({ "text" : markdown}), extra_headers={"Content-Type" : "application/json"}))

        return int(resp_json['id']), int(resp_json['version'])

    async def __update_comment(self, project : str, repo_slug : str, pr_number : str, comment_id : int, comment_version : int, markdown : str) -> tuple[int, int]:
        await self.exec("PUT", f"/rest/api/latest/projects/{project}/repos/{repo_slug}/pull-requests/{pr_number}/comments/{comment_id}", 
                        body=json.dumps({ "version" : comment_version, "text" : markdown}), extra_headers={"Content-Type" : "application/json"})

    async def __find_existing_comment(self, project : str, repo_slug : str, pr_number : str) -> tuple[int, int]:
        cur_page = 0

        async for item in self.__bbdc_paged_items_gen(f"/rest/api/latest/projects/{project}/repos/{repo_slug}/pull-requests/{pr_number}/activities"):
            if 'comment' in item.keys():
                comment = item['comment']

                if 'threadResolved' in comment.keys() and not bool(comment['threadResolved']):
                    if 'permittedOperations' in comment.keys():
                        if 'editable' in comment['permittedOperations'].keys():
                            if bool(comment['permittedOperations']['editable']):
                                if 'text' in comment.keys():
                                    if PullRequestDecoration.matches_identifier(item['comment']['text']):
                                        return int(comment['id']), int(comment['version'])
        return None, None

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, summary_markdown : str):
        id, version = await self.__find_existing_comment(project, repo_slug, pr_number)

        content = full_markdown if len(full_markdown) <= BBDCService.__max_content_chars else summary_markdown

        if id is None and version is None:
            id, version = await self.__add_comment(project, repo_slug, pr_number, content)
        else:
            await self.__update_comment(project, repo_slug, pr_number, id, version, content)

        SCMService.log().debug(f"Comment {id} version {version} modified on PR {pr_number}")
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return self._form_url(f"projects/{project}/repos/{repo_slug}/browse{code_path}", anchor=code_line, at=branch)
   