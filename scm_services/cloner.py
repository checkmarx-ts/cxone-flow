import os, tempfile, shutil, shlex, subprocess, asyncio, logging, urllib, base64, re
from cxoneflow_logging import SecretRegistry
from pathlib import Path

class Cloner:

    __https_matcher = re.compile("^http(s)?")
    __ssh_matcher = re.compile("^ssh")

    __http_protocols = ['http', 'https']
    __ssh_protocols = ['ssh']

    def __init__(self):
        self.__env = dict(os.environ)

    @staticmethod
    def log():
        return logging.getLogger("Cloner")

    @staticmethod
    def __insert_creds_in_url(url, username, password):
        split = urllib.parse.urlsplit(url)
        new_netloc = f"{urllib.parse.quote(username, safe='') if username is not None else 'git'}:{SecretRegistry.register(urllib.parse.quote(password, safe=''))}@{split.netloc}"
        return urllib.parse.urlunsplit((split.scheme, new_netloc, split.path, split.query, split.fragment))
        
    @staticmethod
    def using_basic_auth(username, password, in_header=False):
        Cloner.log().debug("Clone config: using_basic_auth")

        retval = Cloner()
        retval.__protocol_matcher = Cloner.__https_matcher
        retval.__supported_protocols = Cloner.__http_protocols
        retval.__port = None
        retval.__username = username
        retval.__password = SecretRegistry.register(password)

        if not in_header:
            retval.__clone_cmd_stub = ["git", "clone"]
            retval.__fix_clone_url = lambda url: Cloner.__insert_creds_in_url(url, username, password)
        else:
            encoded_creds = SecretRegistry.register(base64.b64encode(f"{username}:{password}".encode('UTF8')).decode('UTF8'))
            retval.__clone_cmd_stub = ["git", "clone", "-c", f"http.extraHeader=Authorization: Basic {encoded_creds}"]
            retval.__fix_clone_url = lambda url: url

        return retval

    @staticmethod
    def using_token_auth(token):
        Cloner.log().debug("Clone config: using_token_auth")

        retval = Cloner()
        retval.__protocol_matcher = Cloner.__https_matcher
        retval.__supported_protocols = Cloner.__http_protocols
        retval.__port = None

        retval.__clone_cmd_stub = ["git", "clone", "-c", f"http.extraHeader=Authorization: Bearer {token}"]

        retval.__fix_clone_url = lambda url: url

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

        retval.__env['GIT_SSH_COMMAND'] = f"ssh -i '{shlex.quote(retval.__keyfile)}' -oIdentitiesOnly=yes -oStrictHostKeyChecking=accept-new -oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedAlgorithms=+ssh-rsa"
        retval.__clone_cmd_stub = ["git", "clone"]

        retval.__fix_clone_url = lambda url: url

        return retval
   
    def select_protocol_from_supported(self, protocol_list):
        for x in protocol_list:
            if self.__protocol_matcher.match(x):
                return x
        return None
    
    @property
    def supported_protocols(self):
        return self.__supported_protocols

    @property
    def destination_port(self):
        return self.__port

    def clone(self, clone_url):
        Cloner.log().debug(f"Clone Execution for: {clone_url}")

        fixed_clone_url = self.__fix_clone_url(clone_url)
        clone_output_loc = tempfile.TemporaryDirectory(delete=False)
        cmd = self.__clone_cmd_stub + [fixed_clone_url, clone_output_loc.name]
        Cloner.log().debug(cmd)
        thread = asyncio.to_thread(subprocess.run, cmd, capture_output=True, env=self.__env, check=True)
        
        return Cloner.__clone_worker(thread, clone_output_loc)

    async def reset_head(self, code_path, hash):
        try:
            result = await (asyncio.to_thread(subprocess.run, ["git", "reset", "--hard", hash], \
                                capture_output=True, env=self.__env, check=True, cwd=code_path))
            
            self.log().debug(f"Reset task: return code [{result.returncode}] stdout: [{result.stdout}] stderr: [{result.stderr}]")

        except subprocess.CalledProcessError as ex:
            self.log().error(f"{ex} stdout: [{ex.stdout.decode('UTF-8')}] stderr: [{ex.stderr.decode('UTF-8')})]")
            raise

    class __clone_worker:

        def __init__(self, clone_thread, clone_dest_path):
            self.__log = logging.getLogger(f"__clone_worker:{clone_dest_path}")
            self.__clone_out_tempdir = clone_dest_path
            self.__clone_thread = clone_thread

        
        async def loc(self):
            try:
                completed = await self.__clone_thread
                self.__log.debug(f"Clone task: return code [{completed.returncode}] stdout: [{completed.stdout}] stderr: [{completed.stderr}]")
                return self.__clone_out_tempdir.name
            except subprocess.CalledProcessError as ex:
                self.__log.error(f"{ex} stdout: [{ex.stdout.decode('UTF-8')}] stderr: [{ex.stderr.decode('UTF-8')})]")
                raise

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self.__log.debug(f"Cleanup: {self.__clone_out_tempdir}")
            self.__clone_out_tempdir.cleanup()



