from .resolver_runner import ResolverRunner
from .resolver_opts import ResolverOpts
from typing import List
import os


class ShellRunner(ResolverRunner):

    __resolver_name = "ScaResolver"

    def __init__(self, workpath: str, opts: ResolverOpts, resolver_path: str):
        super().__init__(workpath, opts)
        self.__resolver_path = resolver_path

    def _get_resolver_exec_cmd(self) -> List[str]:
        cmd = None

        if self.__resolver_path is not None and (
            os.path.exists(self.__resolver_path)
            and os.path.isfile(self.__resolver_path)
        ):
            cmd = [self.__resolver_path]
        elif os.path.exists(ShellRunner.__resolver_name):
            cmd = [ShellRunner.__resolver_name]

        return cmd
