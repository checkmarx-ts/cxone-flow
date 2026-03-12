from workflows.messaging import PRDetails
from scm_services.scm import SCMService
from api_utils import form_url
from jsonpath_ng import parse



class AbstractGHService(SCMService):
    __pr_head_sha_query = parse("$.pull_request.head.sha")
    
    def _get_head_sha(self, pr_details : PRDetails) -> str:
        found = AbstractGHService.__pr_head_sha_query.find(pr_details.event_context.message)

        return found.pop().value

    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")
