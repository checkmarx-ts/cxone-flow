from .scm import SCMService
from scm_services.cloner import Cloner
from typing import Dict


class GHService(SCMService):
    __max_content_chars = 65535

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, 
        summary_markdown : str, event_msg : Dict=None):
        raise NotImplementedError("exec_pr_decorate")
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        raise NotImplementedError("create_code_permalink")
