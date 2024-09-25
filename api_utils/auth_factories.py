from requests.auth import AuthBase
from requests import request
from typing import Dict
from jsonpath_ng import parse
import jwt, time, asyncio, logging, json, re
from datetime import datetime
from threading import Lock
from _agent import __agent__
from api_utils.bearer import HTTPBearerAuth
from cxone_api.util import json_on_ok
from cxoneflow_logging import SecretRegistry
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json

class AuthFactoryException(BaseException):
    pass

@dataclass_json
@dataclass
class EventContext:
    raw_event_payload : bytes = field(repr=False)
    headers : Dict
    message : Dict = field(init=False)

    def __post_init__(self):
        self.message = json.loads(self.raw_event_payload)


class HeaderFilteredEventContext(EventContext):
    def __init__(self, raw_event_payload : str, headers : Dict, header_key_regex : str):
        pattern = re.compile(header_key_regex)
        EventContext.__init__(self, raw_event_payload=raw_event_payload, headers={k:v for k,v in headers if pattern.match(k)})




class AuthFactory:
    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    async def get_auth(self, event_context : EventContext=None, force_reauth : bool=False) -> AuthBase:
        raise NotImplementedError("get_auth")

    async def get_token(self, event_context : EventContext=None, force_reauth : bool=False) -> str:
        raise NotImplementedError("get_token")
    

class StaticAuthFactory(AuthFactory):
    def __init__(self, static_auth : AuthBase):
        self.__auth = static_auth

    async def get_auth(self, event_context : EventContext=None, force_reauth : bool=False) -> AuthBase:
        return self.__auth


class GithubAppAuthFactory(AuthFactory):
    __lock = Lock()

    __token_cache = {}

    __event_installation_id = parse("$.installation.id")
    __app_id_header = "X-Github-Hook-Installation-Target-Id"


    def __init__(self, private_key : str, api_url : str):
        self.__pkey = private_key
        self.__api_url = api_url

    def __encoded_jwt_factory(self, install_id : int) -> str:
        payload = {
            'iat' : int(time.time()),
            "exp" : int(time.time()) + 600,
            'iss' : install_id,
            'alg' : "RS256"
        }

        return jwt.encode(payload, self.__pkey, algorithm='RS256')
    
    async def __get_token_tuple(self, event_context : EventContext=None, force_reauth : bool=False):

        install_id_found = GithubAppAuthFactory.__event_installation_id.find(event_context.message)
        if len(install_id_found) == 0:
            raise AuthFactoryException("GitHub installation id was not found in the event payload.")
        install_id = install_id_found[0].value

        if GithubAppAuthFactory.__app_id_header in event_context.headers.keys():
            app_id = event_context.headers[GithubAppAuthFactory.__app_id_header]
        else:
            raise AuthFactoryException(f"Header {GithubAppAuthFactory.__app_id_header} not found in event context.")

        token_tuple = None
        
        with GithubAppAuthFactory.__lock:
            if install_id in GithubAppAuthFactory.__token_cache.keys():
                token_tuple = tuple(GithubAppAuthFactory.__token_cache[install_id])
                exp = token_tuple[1]
                if datetime.now(exp.tzinfo) >= exp:
                    GithubAppAuthFactory.log().debug(f"Token for app_id {app_id} install_id {install_id} expired at {exp}")
                    token_tuple = None

        if token_tuple is None or force_reauth:    
            GithubAppAuthFactory.log().debug(f"Generating app token for app_id {app_id} install_id {install_id}")
            token_response = json_on_ok(await asyncio.to_thread(request, method="POST", 
                                        url=f"{self.__api_url.rstrip("/")}/app/installations/{install_id}/access_tokens",
                                        headers = {"User-Agent" : __agent__}, 
                                        auth=HTTPBearerAuth(self.__encoded_jwt_factory(app_id))))
            GithubAppAuthFactory.log().debug(f"App token for app_id {app_id} install_id {install_id} generated.")
            
            token_tuple = (SecretRegistry.register(token_response['token']), datetime.fromisoformat(token_response['expires_at']))
            
            with GithubAppAuthFactory.__lock:
                GithubAppAuthFactory.__token_cache[install_id] = token_tuple
            
        return token_tuple

    async def get_auth(self, event_context : EventContext=None, force_reauth : bool=False) -> AuthBase:
        if event_context is None:
            raise AuthFactoryException("Event context is required.")
        return HTTPBearerAuth ((await self.__get_token_tuple(event_context, force_reauth))[0])

    async def get_token(self, event_context : EventContext=None, force_reauth : bool=False) -> str:
        if event_context is None:
            raise AuthFactoryException("Event context is required.")
        return (await self.__get_token_tuple(event_context, force_reauth))[0]




