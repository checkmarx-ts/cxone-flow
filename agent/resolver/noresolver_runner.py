
from agent.resolver.resolver_runner import ResolverRunner, ResolverExecutionContext
import subprocess
from typing import List


class NoResolverExecutionContext(ResolverExecutionContext):
    def _get_resolver_exec_cmd(self) -> List[str]:
       return []

    async def execute_resolver(
        self, project_name: str, exclusions: str
    ) -> subprocess.CompletedProcess:
       return subprocess.CompletedProcess(None, 0)


class NoResolverRunner(ResolverRunner):

  def __init__(self):
     super().__init__(None, None)
    
  async def executor(self):
      return NoResolverExecutionContext(None, None)
