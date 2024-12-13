from .. import DictCmdLineOpts


class ResolverOpts(DictCmdLineOpts):
      
    __forbidden_opts = [
        "a",
        "account",
        "scan-path",
        "containers-result-path",
        "resolver-result-path",
        "project-name",
        "authentication-server-url",
        "p",
        "password",
        "sso-provider",
        "sca-app-url",
        "s",
        "scan-path",
        "server-url",
        "u",
        "username",
        "project-tags",
        "scan-tags",
        "bypass-exitcode",
        "no-upload-manifest",
        "help",
        "manifests-path",
        "t",
        "project-teams",
        "q",
        "quiet",
        "save-evidence-path",
        "severity-threshold",
        "report-content",
        "report-extension",
        "report-path",
        "report-type",
        "sast-result-path",
        "cxpassword",
        "cxuser",
        "cxprojectid",
        "cxprojectname",
        "cxserver"
    ]

    def _validate_arg(self, arg_name: str, arg_value: str) -> bool:
        
        return not arg_name in ResolverOpts.__forbidden_opts
