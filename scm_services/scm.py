import asyncio, logging
from requests import Request


class SCMAuthException(Exception):
    pass

class RetriesExhausted(Exception):
    pass


class SCMService:

    @staticmethod
    def log():
        return logging.getLogger(__name__)

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
    
    def __form_url(self, path):
        base = self.__session.base_endpoint.rstrip("/")
        suffix = path.lstrip("/")
        return f"{base}/{suffix}"
    
    
    async def _exec(self, method, path, query=None, body=None, extra_headers=None):
        return await self.__exec_request(Request(method=method, \
                                                url = self.__form_url(path), \
                                                params=query, \
                                                data=body, \
                                                auth=self.__session.auth, \
                                                headers = extra_headers))
    
    async def get_protected_branches(self, project, slug):
        raise NotImplementedError("get_protected_branches")

    async def get_default_branch(self, project, slug):
        raise NotImplementedError("get_default_branch")
    
    async def validate_signature(self, headers, raw_payload):
        raise NotImplementedError("validate_signature")



