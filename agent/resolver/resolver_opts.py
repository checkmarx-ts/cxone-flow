from dataclasses import dataclass


@dataclass(frozen=True)
class ResolverOpts:
      persistent_log_path : str
      fail_on_manifest_failure : bool
      verbose_logging : bool
      scan_containers : bool
      ssl_verify : bool
      proxy : str
