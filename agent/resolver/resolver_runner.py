from typing import List
from .resolver_opts import ResolverOpts
import subprocess, logging, asyncio, tempfile, os
from .exceptions import ResolverAgentException


class ResolverRunner:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, workpath: str, opts: ResolverOpts):
        self.__workpath = workpath.rstrip("/") + "/"
        self.__opts = opts

    @property
    def can_execute(self):
        return not self._get_resolver_exec_cmd() == None

    @property
    def work_root(self) -> tempfile.TemporaryDirectory:
        if self.__work_root is None:
            raise ResolverAgentException("Not executing in 'with' scope.")

        return self.__work_root

    @property
    def clone_path(self) -> str:
        return self.work_root.name.rstrip("/") + "/clone/"

    @property
    def _resolver_loc(self) -> str:
        return self.work_root.name.rstrip("/") + "/resolver"

    @property
    def _container_loc(self) -> str:
        return self.work_root.name.rstrip("/") + "/container"

    @property
    def resolver_out_file(self) -> str:
        return self._resolver_loc + "/resolver.json"

    @property
    def container_out_file(self) -> str:
        return self._resolver_loc + "/container.json"

    def _get_resolver_exec_cmd(self) -> List[str]:
        raise NotImplemented("_get_resolver_exec_cmd")

    async def _execute_cmd(self, args: List[str]) -> subprocess.CompletedProcess:
        return await asyncio.to_thread(
            subprocess.run,
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )

    async def execute_resolver(self, project_name: str) -> subprocess.CompletedProcess:
        cmd = self._get_resolver_exec_cmd()

        exec_opts = (
            ["offline"]
            + self.__opts.as_args()
            + [
                "--scan-path",
                self.clone_path,
                "--containers-result-path",
                self.container_out_file,
                "--resolver-result-path",
                self.resolver_out_file,
                "--project-name",
                project_name,
            ]
        )

        self.log().debug(f"Running resolver: {cmd + exec_opts}")

        resolver_exec_result = await self._execute_cmd(cmd + exec_opts)

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
