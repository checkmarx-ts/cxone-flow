from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ResolverOpts:
      persistent_log_path : str
      fail_on_manifest_failure : bool
      verbose_logging : bool
      scan_containers : bool
      proxy : str

      def as_args(self) -> List[str]:
            s = []

            if self.persistent_log_path is not None:
                  s.append("--logs-path")
                  s.append(self.persistent_log_path)
            
            if self.fail_on_manifest_failure:
                  s.append("--break-on-manifest-failure")
            
            if self.verbose_logging:
                  s.append("--log-level")
                  s.append("Verbose")

            if self.scan_containers:
                  s.append("--scan-containers")
           
            if self.proxy is not None:
                  s.append("--proxies")
                  s.append(self.proxy)


            return s

