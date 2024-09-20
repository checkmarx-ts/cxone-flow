from _agent import __agent__
from requests import Response
from requests import request
from typing import Dict, Union, Any
import urllib, logging, sys, asyncio
from api_utils import AuthFactory

class SCMAuthException(Exception):
    pass

class RetriesExhausted(Exception):
    pass

class APISession:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, api_base_endpoint : str, api_suffix : str, auth : AuthFactory, timeout : int = 60, retries : int = 3, proxies : Dict = None, ssl_verify : Union[bool, str] = True):

        self.__headers = { "User-Agent" : __agent__ }
        
        self.__base_endpoint = api_base_endpoint
        self.__api_suffix = api_suffix
        self.__timeout = timeout
        self.__retries = retries

        self.__verify = ssl_verify
        self.__proxies = proxies
        self.__auth_factory = auth
    
    @property
    def _api_endpoint(self):
        base = self.__base_endpoint.rstrip("/")
        if self.__api_suffix is not None and len(self.__api_suffix) > 0:
            base = f"{base}/{self.__api_suffix.lstrip("/").rstrip("/")}"
        
        return base


    def _form_url(self, url_path, anchor=None, **kwargs):
        base = self._api_endpoint
        suffix = urllib.parse.quote(url_path.lstrip("/"))
        args = [f"{x}={urllib.parse.quote(str(kwargs[x]))}" for x in kwargs.keys()]
        return f"{base}/{suffix}{"?" if len(args) > 0 else ""}{"&".join(args)}{f"#{anchor}" if anchor is not None else ""}"


    async def exec(self, event_msg : Dict, method : str, path : str, query : Dict = None, body : Any = None, extra_headers : Dict = None) -> Response:
        url = self._form_url(path)
        headers = dict(self.__headers)
        if not extra_headers is None:
            headers.update(extra_headers)

        prepStr = f"[{method} {url}]"

        for tryCount in range(0, self.__retries):
            
            APISession.log().debug(f"Executing: {prepStr} #{tryCount}")
            response = await asyncio.to_thread(request, method=method, url=url, params=query,
                data=body, headers=headers, auth=await self.__auth_factory.make_auth(event_msg, self._api_endpoint, tryCount > 0), 
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




