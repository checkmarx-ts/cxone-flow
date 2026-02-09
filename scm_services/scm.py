import logging
from api_utils.apisession import APISession
from scm_services.cloner import Cloner
from typing import Dict, Any, final
from requests import Response
from api_utils.auth_factories import EventContext
from workflows.messaging import PRDetails, ScanMessage
from workflows.pr_content import PullRequestCommentContent

class BasicSCMService:
    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, api_session : APISession, **kwargs):
        super().__init__(**kwargs)
        self.__session = api_session

    @final
    async def exec(self, method : str, path : str, query : Dict=None, body : Any=None, 
                   extra_headers : Dict=None, event_context : EventContext=None, url_vars : Dict = None) -> Response:
        return await self.__session.exec(event_context, method, path, query, body, extra_headers, url_vars)

    def _form_url(self, url_path, anchor=None, **kwargs):
        return self.__session._form_url(url_path, anchor, **kwargs)

class SCMService(BasicSCMService):

    def __init__(self, display_url : str, moniker : str, api_session : APISession, shared_secret : str, cloner : Cloner, **kwargs):
        super().__init__(api_session=api_session, **kwargs)
        self.__shared_secret = shared_secret
        self.__cloner = cloner
        self.__moniker = moniker
        self.__display_url = display_url

    @property
    def display_url(self) -> str:
        return self.__display_url
    
    @property
    def moniker(self) -> str:
        return self.__moniker

    @property
    def cloner(self) -> Cloner:
        return self.__cloner
    
    @property
    def shared_secret(self) -> str:
        return self.__shared_secret

    async def exec_pr_scan_update_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_update_decorate")
    
    async def exec_pr_scan_pending_decorate(self, pr_details : PRDetails, content: PullRequestCommentContent):
        raise NotImplementedError("exec_pr_scan_pending_decorate")

    async def exec_pr_scan_failure_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_failure_decorate")

    async def exec_pr_scan_success_decorate(self, pr_details : PRDetails, content : PullRequestCommentContent, scan_details : ScanMessage):
        raise NotImplementedError("exec_pr_scan_success_decorate")

    async def exec_pr_unrecoverable_error(self, pr_details : PRDetails, scan_details : ScanMessage, fail_msg : str):
        raise NotImplementedError("exec_pr_unrecoverable_error")

    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        raise NotImplementedError("create_code_permalink")
   



