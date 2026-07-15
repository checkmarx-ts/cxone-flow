import json
from typing import Union, Coroutine
from cxone_api.util import json_on_ok
from scm_services.scm import SCMService
from workflows.pr_content import PullRequestCommentContent
from workflows.messaging import PRDetails, ScanMessage
from workflows.pr_content import PullRequestAbstractMarkdownComment
from api_utils import form_url


class BBCService(SCMService):
  __max_content_chars = 32767

  async def __page_gen(self, path):
      fetch_page = 1
      buf = []
      end = False

      while True:
          if len(buf) == 0 and not end:
              json = json_on_ok(await self.exec("GET", path, {"page" : fetch_page}))
              buf = json['values']
              
              if buf is None or len(buf) == 0:
                  return
              else:
                  if json.get("next") is None:
                    end = True
                  else:
                      fetch_page += 1
          elif len(buf) == 0 and end:
              return

          yield buf.pop()
  
  async def __find_existing_comment(self, organization : str, repo_slug : str, pr_number : str) -> Union[int, None]:
    async for comment in self.__page_gen(f"/repositories/{organization}/{repo_slug}/pullrequests/{pr_number}/comments"):
      content = comment.get("content", {}).get("raw", None)
      if content is not None and PullRequestAbstractMarkdownComment.comment_matches_identifier(content):
         return comment.get("id")

  async def __mutate_comment(self, exec_coroutine : Coroutine):
    response = await exec_coroutine

    if not response.ok:
      BBCService.log().error(f"Response of {response.status_code} from {response.request.url}")
    else:
      comment = response.json()
      BBCService.log().debug(f"Comment {comment.get("id", "Unknown")} modified: {response.request.url}")

  async def __add_comment(self, organization : str, repo_slug : str, pr_number : str, content : str):
    payload = {"content" : {
      "raw" : content
    }}

    await self.__mutate_comment(self.exec("POST", f"/repositories/{organization}/{repo_slug}/pullrequests/{pr_number}/comments", 
                               body=json.dumps(payload), extra_headers={"Content-Type" : "application/json"}))


  async def __update_comment(self, organization : str, repo_slug : str, pr_number : str, comment_id : int, content : str):
    payload = {"content" : {
      "raw" : content
    }}

    await self.__mutate_comment(self.exec("PUT", f"/repositories/{organization}/{repo_slug}/pullrequests/{pr_number}/comments/{comment_id}",
                               body=json.dumps(payload), extra_headers={"Content-Type" : "application/json"}))


  async def __create_or_update_comment(self, organization : str, repo_slug : str, pr_number : str, markdown : str):
    existing_id = await self.__find_existing_comment(organization, repo_slug, pr_number)
    if existing_id is None:
       await self.__add_comment(organization, repo_slug, pr_number, markdown)
    else:
       await self.__update_comment(organization, repo_slug, pr_number, existing_id, markdown)

  async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, content.get_content(BBCService.__max_content_chars))
  
  async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, content.get_content(BBCService.__max_content_chars))

  async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, content.get_content(BBCService.__max_content_chars))

  async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, content.get_content(BBCService.__max_content_chars))

  async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, 
                                PullRequestAbstractMarkdownComment.append_comment_identifier(fail_msg))

  async def exec_pr_prescan_failure(self, pr_details : PRDetails, fail_msg : str):
    await self.__create_or_update_comment(pr_details.organization, pr_details.repo_slug, pr_details.pr_id, 
                                PullRequestAbstractMarkdownComment.append_comment_identifier(fail_msg))

  def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
    return form_url(self.display_url, f"/{organization}/{repo_slug}/src/{branch}{code_path}", anchor=f"lines-{code_line}")
