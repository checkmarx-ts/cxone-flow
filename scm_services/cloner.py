import os, tempfile, shutil, shlex, subprocess, asyncio, logging, urllib, base64, re
from cxoneflow_logging import SecretRegistry
from pathlib import Path
from typing import Dict, List
from api_utils.auth_factories import GithubAppAuthFactory
from api_utils.auth_factories import EventContext


class CloneAuthException(BaseException):
    pass

class CloneWorker:

    __stderr_auth_fail = re.compile(".*Invalid username or password.*")
    __auth_fail_exit_code = 128

    def __init__(self, clone_thread, clone_dest_path):
        self.__log = logging.getLogger(f"CloneWorker:{clone_dest_path}")
        self.__clone_out_tempdir = clone_dest_path
        self.__clone_thread = clone_thread

    async def loc(self) -> str:
        try:
            completed = await self.__clone_thread
            self.__log.debug(f"Clone task: return code [{completed.returncode}] stdout: [{completed.stdout}] stderr: [{completed.stderr}]")
            return self.__clone_out_tempdir.name
        except subprocess.CalledProcessError as ex:
            if CloneWorker.__stderr_auth_fail.match(ex.stderr.decode('UTF-8').replace("\n", "")) and \
                ex.returncode == CloneWorker.__auth_fail_exit_code:
                raise CloneAuthException(ex.stderr.decode('UTF-8'))
            else:
                self.__log.error(f"{ex} stdout: [{ex.stdout.decode('UTF-8')}] stderr: [{ex.stderr.decode('UTF-8')})]")
                raise

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.__log.debug(f"Cleanup: {self.__clone_out_tempdir}")
        self.__clone_out_tempdir.cleanup()


class Cloner:
    __https_matcher = re.compile("^http(s)?")
    __ssh_matcher = re.compile("^ssh")

    __http_protocols = ['http', 'https']
    __ssh_protocols = ['ssh']

    def __init__(self):
        self.__additional_env = {}

    @property
    def __running_env(self):
        cur_os_env = dict(os.environ)
        cur_os_env.update(self.__additional_env)

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    @staticmethod
    def insert_creds_in_url(url : str, username : str, password : str) -> str:
        split = urllib.parse.urlsplit(url)
        new_netloc = f"{urllib.parse.quote(username, safe='') if username is not None else 'git'}:{SecretRegistry.register(urllib.parse.quote(password, safe=''))}@{split.netloc}"
        return urllib.parse.urlunsplit((split.scheme, new_netloc, split.path, split.query, split.fragment))
        
    @staticmethod
    def using_basic_auth(username : str, password : str, in_header : bool=False):
        Cloner.log().debug("Clone config: using_basic_auth")


        if not in_header:
            retval = BasicAuthWithCredsInUrl(username, SecretRegistry.register(password))
            retval.__clone_cmd_stub = ["git", "clone"]
        else:
            retval = Cloner()
            encoded_creds = SecretRegistry.register(base64.b64encode(f"{username}:{password}".encode('UTF8')).decode('UTF8'))
            retval.__clone_cmd_stub = ["git", "clone", "-c", f"http.extraHeader=Authorization: Basic {encoded_creds}"]

        retval.__protocol_matcher = Cloner.__https_matcher
        retval.__supported_protocols = Cloner.__http_protocols
        retval.__port = None

        return retval

    @staticmethod
    def using_token_auth(token : str):
        Cloner.log().debug("Clone config: using_token_auth")

        retval = Cloner()
        retval.__protocol_matcher = Cloner.__https_matcher
        retval.__supported_protocols = Cloner.__http_protocols
        retval.__port = None
        retval.__clone_cmd_stub = ["git", "clone", "-c", f"http.extraHeader=Authorization: Bearer {token}"]

        return retval

    @staticmethod
    def using_ssh_auth(ssh_private_key_file : Path, ssh_port : int):
        Cloner.log().debug("Clone config: using_ssh_auth")

        retval = Cloner()
        retval.__protocol_matcher = Cloner.__ssh_matcher
        retval.__supported_protocols = Cloner.__ssh_protocols
        retval.__port = ssh_port
        with open(ssh_private_key_file, "rt") as source:
            with tempfile.NamedTemporaryFile(mode="wt", delete_on_close=False, delete=False) as dest:
                shutil.copyfileobj(source, dest)
                retval.__keyfile = dest.file.name

        retval.__additional_env['GIT_SSH_COMMAND'] = f"ssh -i '{shlex.quote(retval.__keyfile)}' -oIdentitiesOnly=yes -oStrictHostKeyChecking=accept-new -oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedAlgorithms=+ssh-rsa"
        retval.__clone_cmd_stub = ["git", "clone"]

        return retval
    
    @staticmethod
    def using_github_app_auth(gh_auth_factory : GithubAppAuthFactory):
        Cloner.log().debug("Clone config: using_github_app_auth")

        retval = GithubAppCloner(gh_auth_factory)
        retval.__protocol_matcher = Cloner.__https_matcher
        retval.__supported_protocols = Cloner.__http_protocols
        retval.__port = None
        retval.__clone_cmd_stub = ["git", "clone"]

        return retval
   
    def select_protocol_from_supported(self, protocol_list):
        for x in protocol_list:
            if self.__protocol_matcher.match(x):
                return x
        return None
    
    async def _fix_clone_url(self, clone_url : str, event_context : EventContext=None, force_reauth : bool=False):
        return clone_url
    
    @property
    def supported_protocols(self):
        return self.__supported_protocols

    @property
    def destination_port(self):
        return self.__port
    
    async def _get_clone_cmd_stub(self, event_context : Dict=None, api_url : str=None, force_reauth : bool=False) -> List:
        return self.__clone_cmd_stub
    
    async def clone(self, clone_url, event_context : EventContext=None, force_reauth : bool=False) -> CloneWorker:
        Cloner.log().debug(f"Clone Execution for: {clone_url}")

        fixed_clone_url = await self._fix_clone_url(clone_url, event_context, force_reauth)
        clone_output_loc = tempfile.TemporaryDirectory(delete=False)
        cmd = await self._get_clone_cmd_stub(event_context, force_reauth) + [fixed_clone_url, clone_output_loc.name]
        Cloner.log().debug(cmd)
        thread = asyncio.to_thread(subprocess.run, cmd, capture_output=True, env=self.__running_env, check=True)
        
        return CloneWorker(thread, clone_output_loc)

    async def reset_head(self, code_path, hash):
        try:
            result = await (asyncio.to_thread(subprocess.run, ["git", "reset", "--hard", hash], \
                                capture_output=True, env=self.__running_env, check=True, cwd=code_path))
            
            self.log().debug(f"Reset task: return code [{result.returncode}] stdout: [{result.stdout}] stderr: [{result.stderr}]")

        except subprocess.CalledProcessError as ex:
            self.log().error(f"{ex} stdout: [{ex.stdout.decode('UTF-8')}] stderr: [{ex.stderr.decode('UTF-8')})]")
            raise

class BasicAuthWithCredsInUrl(Cloner):
    def __init__(self, username : str, password : str):
        Cloner.__init__(self)
        self.__username = username
        self.__password = password

    async def _fix_clone_url(self, clone_url : str, event_context : EventContext=None, force_reauth : bool=False):
        return Cloner.insert_creds_in_url(clone_url, self.__username, self.__password)


class GithubAppCloner(Cloner):
    def __init__(self, auth_factory : GithubAppAuthFactory):
        Cloner.__init__(self)
        self.__auth_factory = auth_factory

    async def _fix_clone_url(self, clone_url : str, event_context : EventContext=None, force_reauth : bool=False):
        token = SecretRegistry.register(await self.__auth_factory.get_token(event_context, force_reauth))
        return Cloner.insert_creds_in_url(clone_url, "x-access-token", token)
