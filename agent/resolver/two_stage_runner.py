from agent.resolver.resolver_runner import ResolverRunner, ResolverExecutionContext, AbstractRunner
from agent.resolver.resolver_opts import ResolverOpts
from agent.resolver.exceptions import ResolverAgentException
import subprocess, os, asyncio

class ResolverTwoStageExecutionContext(ResolverExecutionContext):
    __docker_cmd = ["docker", "run", "-t", "--rm"]

    def __init__(
        self, workpath: str, opts: ResolverOpts, resolver_runner: ResolverRunner, 
        resolver_before : bool, container_tag : str, shell : str, script : str, run_as_agent : bool):
        super().__init__(workpath, opts)
        self.__resolver = resolver_runner
        self.__resolver_executor = None
        self.__resolver_before = resolver_before
        self.__container_tag = container_tag
        self.__shell = shell
        self.__script = script
        if run_as_agent:
            self.__user_opts = ["-u", f"{os.getuid()}:{os.getgid()}"]
        else:
            self.__user_opts = []

    @property
    def can_execute(self):
        return self.__resolver_executor is not None and self.__resolver_executor.can_execute

    async def execute_resolver(
        self, project_name: str, exclusions: str
    ) -> subprocess.CompletedProcess:
        
        exit_code = 0
        resolver_result = None
        shell_result = None
        result_log = b""

        try:
            if self.__resolver_before:
                try:
                    resolver_result = await self.__resolver_executor.execute_resolver(project_name, exclusions)
                except subprocess.CalledProcessError as cpex:
                    ResolverExecutionContext.log().exception(cpex)
                    resolver_result = subprocess.CompletedProcess(cpex.cmd, cpex.returncode, cpex.stdout)
            
            exit_code = resolver_result.returncode if resolver_result is not None else exit_code

            try:
                exec_command = ResolverTwoStageExecutionContext.__docker_cmd + \
                self.__user_opts + \
                ["-v", f"{self.clone_path}:/code", "-w", "/code",
                "--entrypoint", self.__shell,
                self.__container_tag,
                "-c", self.__script]

                shell_result = await AbstractRunner.execute_cmd_async(exec_command, {"HOME" : "/code"})
            except subprocess.CalledProcessError as cpex:
                ResolverExecutionContext.log().exception(cpex)
                shell_result = subprocess.CompletedProcess(cpex.cmd, cpex.returncode, cpex.stdout)

            exit_code = shell_result.returncode if exit_code == 0 else exit_code

            if not self.__resolver_before:
                try:
                    resolver_result = await self.__resolver_executor.execute_resolver(project_name, exclusions)
                except subprocess.CalledProcessError as cpex:
                    ResolverExecutionContext.log().exception(cpex)
                    resolver_result = subprocess.CompletedProcess(cpex.cmd, cpex.returncode, cpex.stdout)
                 
            exit_code = resolver_result.returncode if exit_code == 0 else exit_code

            if resolver_result.stdout is not None:
                result_log = resolver_result.stdout

            if shell_result.stdout is not None:
                result_log += shell_result.stdout

            ResolverTwoStageExecutionContext.log().info(f"Resolver execution result code: {resolver_result.returncode}, " 
                                                        + f"pre-scan shell exit code: {shell_result.returncode}")
        except asyncio.CancelledError as cex:
          ResolverTwoStageExecutionContext.log().exception(cex)
          raise
        except BaseException as ex:
          ResolverTwoStageExecutionContext.log().exception(ex)
        
        return subprocess.CompletedProcess(None, exit_code, stdout=result_log)

    async def __aenter__(self):
        if self.__resolver_executor is not None:
            raise ResolverAgentException(
                "Resolver executor is already initialized, it should not be."
            )

        await super().__aenter__()
        self.__resolver_executor = await self.__resolver.executor()
        self.__resolver_executor.work_root = self.work_root
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.__resolver_executor = None
        await super().__aexit__(exc_type, exc, tb)
        return self


class ResolverTwoStageRunner(ResolverRunner):
    def __init__(
        self,
        workpath: str,
        opts: ResolverOpts,
        resolver_runner: ResolverRunner,
        run_resolver_before: bool,
        container_tag: str,
        shell: str,
        script: str,
        run_as_agent_user : bool,
    ):
        super().__init__(workpath, opts)
        self.__resolver = resolver_runner
        self.__resolver_before = run_resolver_before
        self.__container_tag = container_tag
        self.__shell = shell
        self.__script = script
        self.__as_agent = run_as_agent_user

    async def executor(self):
        return ResolverTwoStageExecutionContext(
            self.work_path, self.resolver_opts, self.__resolver, self.__resolver_before, self.__container_tag,
            self.__shell, self.__script, self.__as_agent)
