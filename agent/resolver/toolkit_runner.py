from .resolver_runner import ResolverRunner
from .resolver_opts import ResolverOpts
from .exceptions import ResolverAgentException
from typing import List
import os, subprocess
from threading import Lock

class ToolkitRunner(ResolverRunner):

  def __init__(self, workpath : str, opts : ResolverOpts, toolkit_path : str, container_tag : str, inherit_uid : bool, inherit_gid : bool):
    super().__init__(workpath, opts)
    self.__toolkit_path = toolkit_path.rstrip("/") + "/"
    self.__src_container_tag = container_tag
    self.__uid = inherit_uid
    self.__gid = inherit_gid
    self.__lock = Lock()
    self.__run_container_tag = None

    ToolkitRunner.__check_cmd_on_path_or_fail("docker")
    ToolkitRunner.__check_cmd_on_path_or_fail("bash")


  @staticmethod
  def __check_cmd_on_path_or_fail(cmd_name : str):
    if not os.path.exists(cmd_name) and os.path.isfile(cmd_name):
      raise ResolverAgentException(f"The required '{cmd_name}' command was not found on the path.")

  def _get_resolver_exec_cmd(self) -> List[str]:
    return ""
  
  async def __get_build_container_tag(self) -> str:
    with self.__lock:
      if self.__run_container_tag is None:
        build_args = [f"{self.__toolkit_path}autobuild.sh", "-t", self.__src_container_tag, "-d", self.__toolkit_path]

        if self.__uid:
          build_args.append("-u")

        if self.__gid:
          build_args.append("-g")

        self.__run_container_tag = (await self._execute_cmd(build_args)).stdout.decode().rstrip("\n")

    return self.__run_container_tag


  async def execute_resolver(self, project_name: str) -> subprocess.CompletedProcess:

    run_tag = await self.__get_build_container_tag()
    # TODO: Map locations to container
    # TODO: Execute container
    # TODO: Outputs of container should be in the correct place
    return await super().execute_resolver(project_name)

