import logging
from requests import Request
from api_utils import APISession
from scm_services.cloner import Cloner



class SCMService:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, moniker : str, api_session : APISession, shared_secret : str, cloner : Cloner):
        self.__session = api_session
        self.__shared_secret = shared_secret
        self.__cloner = cloner
        self.__moniker = moniker

    @property
    def moniker(self):
        return self.__moniker

    @property
    def cloner(self):
        return self.__cloner
    
    @property
    def shared_secret(self):
        return self.__shared_secret
    
    def _form_url(self, url_path, anchor=None, **kwargs):
        return self.__session._form_url(url_path, anchor, **kwargs)
    
    async def exec(self, method : str, path : str, query=None, body=None, extra_headers=None):
        return await self.__session.exec(method, path, query, body, extra_headers)

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, full_markdown : str, summary_markdown : str):
        raise NotImplementedError("exec_pr_decorate")
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        raise NotImplementedError("create_code_permalink")
   



