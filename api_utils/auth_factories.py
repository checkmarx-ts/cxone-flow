from requests.auth import AuthBase
from requests import request
from typing import Dict
from jsonpath_ng import parse
import jwt, time, asyncio, logging
from datetime import datetime
from threading import Lock
from _agent import __agent__
from api_utils.bearer import HTTPBearerAuth
from cxone_api.util import json_on_ok
from cxoneflow_logging import SecretRegistry

class AuthFactoryException(BaseException):
    pass

class AuthFactory:
    async def make_auth(self, event_context : Dict=None, api_url : str=None, force_reauth : bool=False) -> AuthBase:
        raise NotImplementedError("make_auth")

class StaticAuthFactory(AuthFactory):
    def __init__(self, static_auth : AuthBase):
        self.__auth = static_auth

    async def make_auth(self, event_context : Dict=None, api_url : str=None, force_reauth : bool=False) -> AuthBase:
        return self.__auth


class GithubAppAuthFactory(AuthFactory):
    __lock = Lock()

    __token_cache = {}

    __event_installation_id = parse("$.installation.id")
    __event_app_id = parse("$.sender.id")

    @staticmethod
    def log():
        return logging.getLogger("GithubAppAuthFactory")

    def __init__(self, private_key : str):
        self.__pkey = private_key

    def __encoded_jwt_factory(self, install_id : int) -> str:
        payload = {
            'iat' : int(time.time()),
            "exp" : int(time.time()) + 600,
            'iss' : install_id,
            'alg' : "RS256"
        }

        return jwt.encode(payload, self.__pkey, algorithm='RS256')

    async def make_auth(self, event_context : Dict=None, api_url : str=None, force_reauth : bool=False) -> AuthBase:
        if event_context is None or api_url is None:
            raise AuthFactoryException("Event context and API url are required.")
                
        install_id_found = GithubAppAuthFactory.__event_installation_id.find(event_context)
        if len(install_id_found) == 0:
            raise AuthFactoryException("GitHub installation id was not found in the event payload.")
        install_id = install_id_found[0].value

        app_id_found = GithubAppAuthFactory.__event_app_id.find(event_context)
        if len(app_id_found) == 0:
            raise AuthFactoryException("GitHub app id was not found in the event payload.")
        app_id = app_id_found[0].value

        token_tuple = None

        
        with GithubAppAuthFactory.__lock:
            if install_id in GithubAppAuthFactory.__token_cache.keys():
                token_tuple = tuple(GithubAppAuthFactory.__token_cache[install_id])
                exp = token_tuple[1]
                if datetime.now(exp.tzinfo) >= exp:
                    token_tuple = None

        if token_tuple is None or force_reauth:        
            token_response = json_on_ok(await asyncio.to_thread(request, method="POST", url=f"{api_url.rstrip("/")}/app/installations/{install_id}/access_tokens",
                                        headers = {"User-Agent" : __agent__}, 
                                        auth=HTTPBearerAuth(self.__encoded_jwt_factory(app_id))))
            
            token_tuple = (SecretRegistry.register(token_response['token']), datetime.fromisoformat(token_response['expires_at']))
            
            with GithubAppAuthFactory.__lock:
                GithubAppAuthFactory.__token_cache[install_id] = token_tuple


        return HTTPBearerAuth (token_tuple[0])




