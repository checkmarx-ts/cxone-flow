import asyncio, logging, urllib
from requests import Request


class SCMAuthException(Exception):
    pass

class RetriesExhausted(Exception):
    pass


class SCMService:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, moniker, api_session, shared_secret, cloner):
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

    async def __exec_request(self, request):
        prepared_request = self.__session.prepare_request(request)
        prepStr = f"[{prepared_request.method} {prepared_request.url}]"

        for tryCount in range(0, self.__session.retries):
            
            SCMService.log().debug(f"Executing: {prepStr} #{tryCount}")
            response = await asyncio.to_thread(self.__session.send, prepared_request)
            
            logStr = f"{response.status_code}: {response.reason} {prepStr}"
            SCMService.log().debug(f"Response: {logStr} #{tryCount}")

            if not response.ok:
                if response.status_code in [401, 403]:
                    SCMService.log().error(f"{prepStr} : Raising authorization exception, not retrying.")
                    raise SCMAuthException(logStr)
                else:
                    SCMService.log().error(f"{logStr} : Attempt {tryCount}")
            else:
                return response

        raise RetriesExhausted(f"Retries exhausted for {prepStr}")
    
    def _form_url(self, url_path, anchor=None, **kwargs):
        base = self.__session.base_endpoint.rstrip("/")
        suffix = urllib.parse.quote(url_path.lstrip("/"))
        args = [f"{x}={urllib.parse.quote(str(kwargs[x]))}" for x in kwargs.keys()]
        return f"{base}/{suffix}{"?" if len(args) > 0 else ""}{"&".join(args)}{f"#{anchor}" if anchor is not None else ""}"
    
    
    async def exec(self, method, path, query=None, body=None, extra_headers=None):
        return await self.__exec_request(Request(method=method, \
                                                url = self._form_url(path), \
                                                params=query, \
                                                data=body, \
                                                auth=self.__session.auth, \
                                                headers = extra_headers))
    

    async def exec_pr_decorate(self, organization : str, project : str, repo_slug : str, pr_number : str, scanid : str, markdown : str):
        raise NotImplementedError("exec_pr_decorate")
   
    def create_code_permalink(self, organization : str, project : str, repo_slug : str, branch : str, code_path : str, code_line : str):
        raise NotImplementedError("create_code_permalink")
   



