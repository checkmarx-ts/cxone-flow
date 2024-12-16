from typing import List
from .resolver_opts import ResolverOpts
import subprocess, logging, asyncio, tempfile, os
from .exceptions import ResolverAgentException


class ExecutionContext:

    def __init__(self, workpath: str, opts: ResolverOpts):
        self.__workpath = workpath.rstrip("/") + "/"
        self.__opts = opts

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    @property
    def work_root(self) -> tempfile.TemporaryDirectory:
        if self.__work_root is None:
            raise ResolverAgentException("Not executing in 'with' scope.")

        return self.__work_root

    @property
    def clone_directory(self):
        return "clone"

    @property
    def clone_path(self) -> str:
        return self.work_root.name.rstrip("/") + "/" + self.clone_directory
    
    @property
    def execution_clone_path(self) -> str:
        return self.clone_path

    @property
    def resolver_result_directory(self):
        return "resolver"
    
    @property
    def _resolver_loc(self) -> str:
        return self.work_root.name.rstrip("/") + "/" + self.resolver_result_directory

    @property
    def container_result_directory(self):
        return "container"

    @property
    def _container_loc(self) -> str:
        return self.work_root.name.rstrip("/") + "/" + self.container_result_directory

    @property
    def resolver_result_filename(self) -> str:
        return "resolver.json"

    @property
    def container_result_filename(self) -> str:
        return "container.json"

    @property
    def result_resolver_out_file_path(self) -> str:
        return self._resolver_loc + "/" + self.resolver_result_filename

    @property
    def execution_resolver_out_file_path(self) -> str:
        return self.result_resolver_out_file

    @property
    def result_container_out_file_path(self) -> str:
        return self._container_loc + "/" + self.container_result_filename

    @property
    def execution_container_out_file_path(self) -> str:
        return self.result_container_out_file

    @property
    def can_execute(self):
        return not self._get_resolver_exec_cmd() == None

    def _get_resolver_exec_cmd(self) -> List[str]:
        raise NotImplemented("_get_resolver_exec_cmd")


    async def execute_resolver(self, project_name: str) -> subprocess.CompletedProcess:
        cmd = self._get_resolver_exec_cmd()

        exec_opts = (
            ["offline"]
            + self.__opts.as_args()
            + [
                "--scan-path",
                self.execution_clone_path,
                "--containers-result-path",
                self.execution_container_out_file_path,
                "--resolver-result-path",
                self.execution_resolver_out_file_path,
                "--project-name",
                project_name,
            ]
        )

        self.log().debug(f"Running resolver: {cmd + exec_opts}")

        resolver_exec_result = await ResolverRunner.execute_cmd_async(cmd + exec_opts)

        self.log().debug(f"Resolver finished: {resolver_exec_result}")

        return resolver_exec_result

    async def __aenter__(self):
        self.__work_root = tempfile.TemporaryDirectory(
            delete=False, prefix=self.__workpath
        )
        os.mkdir(self.clone_path)
        os.mkdir(self._resolver_loc)
        os.mkdir(self._container_loc)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.log().debug(f"Cleanup: {self.__work_root}")
        self.__work_root.cleanup()
        self.__work_root = None


class ResolverRunner:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, workpath: str, opts: ResolverOpts):
        self.__workpath = workpath.rstrip("/") + "/"
        self.__opts = opts

    @property
    def work_path(self) -> str:
        return self.__workpath

    @property
    def resolver_opts(self) -> ResolverOpts:
        return self.__opts

    @staticmethod
    async def execute_cmd_async(args: List[str]) -> subprocess.CompletedProcess:
        return await asyncio.to_thread(
            subprocess.run,
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )


    @staticmethod
    def execute_cmd(args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True
        )

    async def executor(self):
        raise NotImplemented("executor")
