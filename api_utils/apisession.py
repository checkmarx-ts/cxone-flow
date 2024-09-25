from _agent import __agent__
from requests import Response
from requests import request
from typing import Dict, Union, Any
import logging, sys, asyncio
from api_utils import AuthFactory
from api_utils.auth_factories import EventContext
from . import form_url

class SCMAuthException(Exception):
    pass

class RetriesExhausted(Exception):
    pass

class APISession:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, api_endpoint : str, auth : AuthFactory, timeout : int = 60, retries : int = 3, proxies : Dict = None, ssl_verify : Union[bool, str] = True):

        self.__headers = { "User-Agent" : __agent__ }
        
        self.__api_endpoint = api_endpoint
        self.__timeout = timeout
        self.__retries = retries

        self.__verify = ssl_verify
        self.__proxies = proxies
        self.__auth_factory = auth
    
    @staticmethod
    def form_api_endpoint(base_endpoint : str, suffix : str):
        ret = base_endpoint.rstrip("/")
        if suffix is not None and len(suffix) > 0:
            ret = f"{ret}/{suffix.lstrip("/").rstrip("/")}"
        return ret

    @property
    def api_endpoint(self):
        return self.__api_endpoint

    async def exec(self, event_context : EventContext, method : str, path : str, query : Dict = None, body : Any = None, extra_headers : Dict = None) -> Response:
        url = form_url(self.api_endpoint, path)
        headers = dict(self.__headers)
        if not extra_headers is None:
            headers.update(extra_headers)

        prepStr = f"[{method} {url}]"

        for tryCount in range(0, self.__retries):
            
            APISession.log().debug(f"Executing: {prepStr} #{tryCount}")
            response = await asyncio.to_thread(request, method=method, url=url, params=query,
                data=body, headers=headers, auth=await self.__auth_factory.get_auth(event_context, tryCount > 0), 
                timeout=self.__timeout, proxies=self.__proxies, verify=self.__verify)
            
            logStr = f"{response.status_code}: {response.reason} {prepStr}"
            APISession.log().debug(f"Response #{tryCount}: {logStr} : {response.text}")

            if not response.ok:
                if response.status_code in [401, 403]:
                    APISession.log().error(f"{prepStr} : Raising authorization exception, not retrying.")
                    raise SCMAuthException(logStr)
                else:
                    APISession.log().error(f"{logStr} : Attempt {tryCount}")
                    await asyncio.sleep(1)
            else:
                return response

        raise RetriesExhausted(f"Retries exhausted for {prepStr}")




