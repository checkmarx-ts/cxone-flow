from scm_services.scm import SCMService
from api_utils import form_url



class AbstractGHService(SCMService):
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        return form_url(self.display_url, f"/{organization}/{repo_slug}/blob/{branch}{code_path}", f"L{code_line}")
