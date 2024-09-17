from .cloner import Cloner
from requests.auth import AuthBase
from .scm import SCMService
from .adoe import ADOEService
from .bbdc import BBDCService
from .gh import GHService
from api_utils import auth_basic, auth_bearer

class ScmCloneAuthSupportException(Exception):
        pass


def bitbucketdc_cloner_factory(username=None, password=None, token=None, ssh_path=None, ssh_port=None, oauth_secret : str=None, oauth_id : str=None) -> Cloner:
        if oauth_secret is not None or oauth_id is not None:
                raise ScmCloneAuthSupportException("OAuth clone authentication not supported for BBDC")

        if username is not None and password is not None:
                return Cloner.using_basic_auth(username, password, True) 

        if token is not None:
                return Cloner.using_token_auth(token, username)

        if ssh_path is not None:
                return Cloner.using_ssh_auth(ssh_path, ssh_port)

        return None        

def adoe_cloner_factory(username=None, password=None, token=None, ssh_path=None, ssh_port=None, oauth_secret : str=None, oauth_id : str=None) -> Cloner:
        if oauth_secret is not None or oauth_id is not None:
                raise ScmCloneAuthSupportException("OAuth clone authentication not supported for ADO")

        if username is not None and password is not None:
                return Cloner.using_basic_auth(username, password, True) 

        if token is not None:
                return Cloner.using_basic_auth("", token, True)

        if ssh_path is not None:
                return Cloner.using_ssh_auth(ssh_path, ssh_port)


def gh_cloner_factory(username=None, password=None, token=None, ssh_path=None, ssh_port=None, oauth_secret : str=None, oauth_id : str=None) -> Cloner:
        return Cloner()


class ScmApiAuthSupportException(Exception):
        pass


def adoe_api_auth_factory(username : str=None, password : str=None, token : str=None, oauth_secret : str=None, oauth_id : str=None) -> AuthBase:
        if oauth_secret is not None or oauth_id is not None:
                raise ScmApiAuthSupportException("OAuth API authentication not supported for ADO")
        
        if token is not None:
                return auth_basic("", token)
        elif username is not None and password is not None:
                return auth_basic(username, password)
        else:
                raise ScmApiAuthSupportException("Unable to determine API auth method.")


def bbdc_api_auth_factory(username=None, password=None, token=None, oauth_secret : str=None, oauth_id : str=None) -> AuthBase:
        if oauth_secret is not None or oauth_id is not None:
                raise ScmApiAuthSupportException("OAuth API authentication not supported for BBDC")

        if token is not None:
                return auth_bearer(token)
        elif username is not None and password is not None:
                return auth_basic(username, password)
        else:
                raise ScmApiAuthSupportException("Unable to determine API auth method.")

def github_api_auth_factory(username=None, password=None, token=None, oauth_secret : str=None, oauth_id : str=None) -> AuthBase:
        if token is not None:
                return auth_bearer(token)
        elif username is not None and password is not None:
                return auth_basic(username, password)
        elif oauth_id is not None and oauth_secret is not None:
                pass
        else:
                raise ScmApiAuthSupportException("Unable to determine API auth method.")

