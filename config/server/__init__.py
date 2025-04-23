from _version import __version__
from _agent import __agent__
from pathlib import Path
from .. import ConfigurationException, RouteNotFoundException, CommonConfig
import re, uuid
from scm_services import SCMService, ADOEService, BBDCService, GHService, GLService
from scm_services.cloner import Cloner
from api_utils import auth_basic, auth_bearer
from api_utils.apisession import APISession
from api_utils.auth_factories import AuthFactory, GithubAppAuthFactory
from cxone_service import CxOneService
from password_strength import PasswordPolicy
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService
from workflows.pull_request import PullRequestWorkflow
from workflows.resolver_workflow import (
    DummyResolverScanningWorkflow,
    ResolverScanningWorkflow,
)
from workflows import ResultSeverity, ResultStates
from services import CxOneFlowServices
from typing import List, Dict, Union
from cxone_api import CxOneClient
from kickoff_services import DummyKickoffService, KickoffService


class CxOneFlowConfig(CommonConfig):
    __shared_secret_policy = PasswordPolicy.from_names(
        length=20, uppercase=3, numbers=3, special=2
    )

    @staticmethod
    def get_service_monikers():
        return list(CxOneFlowConfig.__scm_services_config_by_service_moniker.keys())

    @staticmethod
    def retrieve_services_by_moniker(moniker: str) -> CxOneFlowServices:
        return CxOneFlowConfig.__scm_services_config_by_service_moniker[moniker]

    @staticmethod
    def retrieve_scm_services(scm_config_key: str) -> List[SCMService]:
        return [
            entry.scm
            for entry in CxOneFlowConfig.__ordered_scm_services_config[scm_config_key]
        ]

    @staticmethod
    def retrieve_services_by_route(
        clone_urls: str, scm_config_key: str
    ) -> Union[CxOneFlowServices, None]:
        
        if scm_config_key not in CxOneFlowConfig.__ordered_scm_services_config.keys():
            return None
        
        if type(clone_urls) is list:
            it_list = clone_urls
        else:
            it_list = [clone_urls]

        for url in it_list:
            for entry in CxOneFlowConfig.__ordered_scm_services_config[scm_config_key]:
                if entry.matcher.match(url):
                    return entry

        CxOneFlowConfig.log().error(f"No route matched for {clone_urls}")
        raise RouteNotFoundException(clone_urls)

    @staticmethod
    def get_base_url():
        return CxOneFlowConfig.__server_base_url

    @staticmethod
    def bootstrap(config_file_path="./config.yaml"):

        try:
            CxOneFlowConfig.log().info(f"Loading configuration from {config_file_path}")

            raw_yaml = CommonConfig.load_yaml(config_file_path)

            CxOneFlowConfig.__server_base_url = (
                CxOneFlowConfig._get_value_for_key_or_fail(
                    "", "server-base-url", raw_yaml
                )
            )
            CommonConfig._secret_root = CxOneFlowConfig._get_value_for_key_or_fail(
                "", "secret-root-path", raw_yaml
            )

            if len(raw_yaml.keys() - CxOneFlowConfig.__cloner_factories.keys()) == len(
                raw_yaml.keys()
            ):
                raise ConfigurationException.missing_at_least_one_key_path(
                    "/", CxOneFlowConfig.__cloner_factories.keys()
                )

            for scm in CxOneFlowConfig.__cloner_factories.keys():

                if scm in raw_yaml.keys():
                    index = 0
                    for repo_config_dict in raw_yaml[scm]:

                        services = CxOneFlowConfig.__setup_scm(
                            CxOneFlowConfig.__cloner_factories[scm],
                            CxOneFlowConfig.__api_auth_factories[scm],
                            CxOneFlowConfig.__scm_factories[scm],
                            repo_config_dict,
                            f"/{scm}[{index}]",
                        )

                        if (
                            services.scm.moniker
                            not in CxOneFlowConfig.__scm_services_config_by_service_moniker.keys()
                        ):
                            CxOneFlowConfig.__scm_services_config_by_service_moniker[
                                services.scm.moniker
                            ] = services
                        else:
                            raise ConfigurationException(
                                f"Service {services.scm.moniker} is defined more than once."
                            )

                        if not scm in CxOneFlowConfig.__ordered_scm_services_config:
                            CxOneFlowConfig.__ordered_scm_services_config[scm] = [
                                services
                            ]
                        else:
                            CxOneFlowConfig.__ordered_scm_services_config[scm].append(
                                services
                            )

                        index += 1
        except Exception as ex:
            CxOneFlowConfig.log().exception(ex)
            raise

    @staticmethod
    def __resolver_service_factory(
        cxone_client: CxOneClient, config_path, moniker, **kwargs
    ) -> ResolverScanService:
        if kwargs is None or len(kwargs) == 0:
            return ResolverScanService(
                moniker,
                cxone_client,
                CommonConfig._default_amqp_url,
                None,
                None,
                True,
                DummyResolverScanningWorkflow(),
                None,
                None,
                None,
            )
        else:
            msg_private_key = CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                config_path, "private-key", kwargs
            )

            capture_resolver_logs = CxOneFlowConfig._get_value_for_key_or_default(
                "capture-resolver-logs", kwargs, False
            )

            default_tag = CxOneFlowConfig._get_value_for_key_or_default(
                "default-agent-tag", kwargs, None
            )
            project_tag_key = CxOneFlowConfig._get_value_for_key_or_default(
                "resolver-tag-key", kwargs, "resolver"
            )
            agent_tag_list = list(
                set(
                    CxOneFlowConfig._get_value_for_key_or_default(
                        "allowed-agent-tags", kwargs, []
                    )
                )
            )

            # the default tag must have a tag.
            if default_tag is not None and not default_tag in agent_tag_list:
                raise ConfigurationException.missing_keys(
                    f"{config_path}/allowed-agent-tags", [default_tag]
                )

            amqp_url, amqp_user, amqp_password, ssl_verify = (
                CxOneFlowConfig._load_amqp_settings(config_path, **kwargs)
            )

            scan_retries = CxOneFlowConfig._get_value_for_key_or_default(
                "scan-retries", kwargs, ResolverScanService.DEFAULT_SCAN_RETRIES
            )
            scan_timeout = CxOneFlowConfig._get_value_for_key_or_default(
                "scan-timeout-seconds", kwargs, ResolverScanService.DEFAULT_SCAN_TIMEOUT
            )

            return ResolverScanService(
                moniker,
                cxone_client,
                amqp_url,
                amqp_user,
                amqp_password,
                ssl_verify,
                ResolverScanningWorkflow.from_private_key(
                    capture_resolver_logs,
                    bytes(msg_private_key, "UTF-8"),
                    scan_retries,
                    scan_timeout,
                ),
                default_tag,
                project_tag_key,
                agent_tag_list,
            )

    @staticmethod
    def __pr_feedback_service_factory(
        config_path, moniker, **kwargs
    ) -> PRFeedbackService:
        if kwargs is None or len(kwargs.keys()) == 0:
            return PRFeedbackService(
                moniker,
                CxOneFlowConfig._default_amqp_url,
                None,
                None,
                True,
                CxOneFlowConfig.__server_base_url,
                PullRequestWorkflow(),
            )
        else:

            pr_workflow_dict = CxOneFlowConfig._get_value_for_key_or_default(
                "pull-request", kwargs, {}
            )
            scan_monitor_dict = CxOneFlowConfig._get_value_for_key_or_default(
                "scan-monitor", kwargs, {}
            )

            exclusions_dict = CxOneFlowConfig._get_value_for_key_or_default(
                "exclusions", kwargs, {}
            )
            excluded_states = excluded_severities = []

            try:
                excluded_states = [
                    ResultStates(state)
                    for state in CxOneFlowConfig._get_value_for_key_or_default(
                        "state", exclusions_dict, []
                    )
                ]
            except ValueError as ve:
                raise ConfigurationException(
                    f"{config_path}/exclusions/state {ve}: must be one of {ResultStates.names()}"
                )

            try:
                excluded_severities = [
                    ResultSeverity(sev)
                    for sev in CxOneFlowConfig._get_value_for_key_or_default(
                        "severity", exclusions_dict, []
                    )
                ]
            except ValueError as ve:
                raise ConfigurationException(
                    f"{config_path}/exclusions/severity {ve}: must be one of {ResultSeverity.names()}"
                )

            pr_workflow = PullRequestWorkflow(
                excluded_severities,
                excluded_states,
                CxOneFlowConfig._get_value_for_key_or_default(
                    "enabled", pr_workflow_dict, False
                ),
                int(
                    CxOneFlowConfig._get_value_for_key_or_default(
                        "poll-interval-seconds", scan_monitor_dict, 60
                    )
                ),
                int(
                    CxOneFlowConfig._get_value_for_key_or_default(
                        "scan-timeout-hours", scan_monitor_dict, 48
                    )
                ),
            )

            max_poll_interval = int(
                CxOneFlowConfig._get_value_for_key_or_default(
                    "poll-max-interval-seconds", scan_monitor_dict, 600
                )
            )
            poll_backoff = int(
                CxOneFlowConfig._get_value_for_key_or_default(
                    "poll-backoff-multiplier", scan_monitor_dict, 2
                )
            )

            amqp_url, amqp_user, amqp_password, ssl_verify = (
                CxOneFlowConfig._load_amqp_settings(config_path, **kwargs)
            )

            return PRFeedbackService(
                moniker,
                amqp_url,
                amqp_user,
                amqp_password,
                ssl_verify,
                CxOneFlowConfig.__server_base_url,
                pr_workflow,
                max_poll_interval,
                poll_backoff,
            )

    __ordered_scm_services_config = {}
    __scm_services_config_by_service_moniker = {}

    @staticmethod
    def __scm_api_auth_factory(
        api_url: str, api_auth_factory, config_dict, config_path
    ):
        retval = None

        if config_dict is not None and len(config_dict.keys()) > 0:

            retval = api_auth_factory(api_url, config_path, config_dict)

        if retval is None:
            raise ConfigurationException(
                f"{config_path} SCM API authorization configuration is invalid!"
            )

        return retval

    @staticmethod
    def __cloner_factory(
        api_session: APISession,
        scm_cloner_factory,
        clone_auth_dict,
        config_path,
        ssl_no_verify: bool,
    ):

        retval = scm_cloner_factory(
            api_session,
            Path(CxOneFlowConfig._secret_root),
            clone_auth_dict,
            ssl_no_verify,
        )

        if retval is None:
            raise ConfigurationException(
                f"{config_path} SCM clone authorization configuration is invalid!"
            )

        return retval
    
    @staticmethod
    def __kickoff_service_factory(cxone_client, config_dict, config_path, moniker):
        if config_dict is None:
            return DummyKickoffService()
        
        # Default 3 max concurrent scans with a max of 10
        max_scans = min(10, int(CxOneFlowConfig._get_value_for_key_or_default("max-concurrent-scans", config_dict, 3)))
        # Just in case someone gets funny and uses a 0 or negative number.
        max_scans = max(max_scans, 1)

        return KickoffService(cxone_client,
            CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "ssh-public-key", config_dict),
            moniker, max_scans)

    @staticmethod
    def __setup_scm(
        cloner_factory, api_auth_factory, scm_class, config_dict, config_path
    ) -> CxOneFlowServices:
        repo_matcher = re.compile(
            CxOneFlowConfig._get_value_for_key_or_fail(
                config_path, "repo-match", config_dict
            ),
            re.IGNORECASE,
        )

        if repo_matcher.findall(str(uuid.uuid4())):
            raise ConfigurationException.no_wildcard_routes(f"{config_path}/repo-match")

        service_moniker = CxOneFlowConfig._get_value_for_key_or_fail(
            config_path, "service-name", config_dict
        )

        cxone_client = CxOneFlowConfig._cxone_client_factory(
            f"{config_path}/cxone",
            **(
                CxOneFlowConfig._get_value_for_key_or_fail(
                    config_path, "cxone", config_dict
                )
            ),
        )

        pr_feedback_service = CxOneFlowConfig.__pr_feedback_service_factory(
            f"{config_path}/feedback",
            service_moniker,
            **(
                CxOneFlowConfig._get_value_for_key_or_default(
                    "feedback", config_dict, {}
                )
            ),
        )

        resolver_service = CxOneFlowConfig.__resolver_service_factory(
            cxone_client,
            f"{config_path}/resolver",
            service_moniker,
            **(
                CxOneFlowConfig._get_value_for_key_or_default(
                    "resolver", config_dict, {}
                )
            ),
        )

        scan_config_dict = CxOneFlowConfig._get_value_for_key_or_default(
            "scan-config", config_dict, {}
        )

        cxone_service = CxOneService(
            service_moniker,
            cxone_client,
            CxOneFlowConfig._get_value_for_key_or_default(
                "default-scan-engines", scan_config_dict, {}
            ),
            CxOneFlowConfig._get_value_for_key_or_default(
                "default-scan-tags", scan_config_dict, {}
            ),
            CxOneFlowConfig._get_value_for_key_or_default(
                "default-project-tags", scan_config_dict, {}
            ),
        )

        connection_config_dict = CxOneFlowConfig._get_value_for_key_or_fail(
            config_path, "connection", config_dict
        )

        api_auth_dict = CxOneFlowConfig._get_value_for_key_or_fail(
            f"{config_path}/connection", "api-auth", connection_config_dict
        )

        api_base_url = CxOneFlowConfig._get_value_for_key_or_fail(
            f"{config_path}/connection", "base-url", connection_config_dict
        )

        display_url = CxOneFlowConfig._get_value_for_key_or_default(
            "base-display-url", connection_config_dict, api_base_url
        )

        api_url = APISession.form_api_endpoint(
            api_base_url,
            CxOneFlowConfig._get_value_for_key_or_default(
                "api-url-suffix", connection_config_dict, None
            ),
        )

        ssl_verify = CxOneFlowConfig._get_value_for_key_or_default(
            "ssl-verify",
            connection_config_dict,
            CxOneFlowConfig.get_default_ssl_verify_value(),
        )

        ssl_no_verify_git = (
            not ssl_verify
            if isinstance(ssl_verify, bool)
            else True if ssl_verify.lower() == "false" else False
        )

        api_session = APISession(
            api_url,
            CxOneFlowConfig.__scm_api_auth_factory(
                api_url,
                api_auth_factory,
                api_auth_dict,
                f"{config_path}/connection/api-auth",
            ),
            CxOneFlowConfig._get_value_for_key_or_default(
                "timeout-seconds", connection_config_dict, 60
            ),
            CxOneFlowConfig._get_value_for_key_or_default(
                "retries", connection_config_dict, 3
            ),
            CxOneFlowConfig._get_value_for_key_or_default(
                "proxies", connection_config_dict, None
            ),
            ssl_verify,
        )

        scm_shared_secret = CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
            f"{config_path}/connection", "shared-secret", connection_config_dict
        )
        secret_test_result = CxOneFlowConfig.__shared_secret_policy.test(
            scm_shared_secret
        )
        if not len(secret_test_result) == 0:
            raise ConfigurationException(
                f"{config_path}/connection/shared-secret fails some complexity requirements: {secret_test_result}"
            )

        clone_auth_dict = CxOneFlowConfig._get_value_for_key_or_default(
            "clone-auth", connection_config_dict, None
        )
        clone_config_path = f"{config_path}/connection/clone-auth"
        if clone_auth_dict is None:
            clone_auth_dict = api_auth_dict
            clone_config_path = f"{config_path}/connection/api-auth"

        scm_service = scm_class(
            display_url,
            service_moniker,
            api_session,
            scm_shared_secret,
            CxOneFlowConfig.__cloner_factory(
                api_session,
                cloner_factory,
                clone_auth_dict,
                clone_config_path,
                ssl_no_verify_git,
            ),
        )

        return CxOneFlowServices(
            repo_matcher,
            cxone_service,
            scm_service,
            pr_feedback_service,
            resolver_service,
            CxOneFlowConfig.__kickoff_service_factory(cxone_client,
                CxOneFlowConfig._get_value_for_key_or_default("kickoff", config_dict, None), f"{config_path}/kickoff", service_moniker)
        )

    @staticmethod
    def __has_basic_auth(config_dict: Dict) -> bool:
        if "username" in config_dict.keys() and "password" in config_dict.keys():
            if (
                config_dict["username"] is not None
                and config_dict["password"] is not None
            ):
                return True
        return False

    @staticmethod
    def __has_token_auth(config_dict: Dict) -> bool:
        if "token" in config_dict.keys():
            if config_dict["token"] is not None:
                return True
        return False

    @staticmethod
    def __has_ssh_auth(config_dict: Dict) -> bool:
        if "ssh" in config_dict.keys():
            if config_dict["ssh"] is not None:
                return True
        return False

    @staticmethod
    def __bbdc_cloner_factory(
        api_session: APISession,
        config_path: str,
        config_dict: Dict,
        ssl_no_verify: bool,
    ) -> Cloner:
        if CxOneFlowConfig.__has_basic_auth(config_dict):
            return Cloner.using_basic_auth(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
                ssl_no_verify,
                True,
            )

        if CxOneFlowConfig.__has_token_auth(config_dict):
            return Cloner.using_token_auth(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                ),
                ssl_no_verify,
            )

        if CxOneFlowConfig.__has_ssh_auth(config_dict):
            return Cloner.using_ssh_auth(
                Path(CxOneFlowConfig._secret_root)
                / Path(
                    CxOneFlowConfig._get_value_for_key_or_fail(
                        config_path, "ssh", config_dict
                    )
                ),
                config_dict["ssh-port"] if "ssh-port" in config_dict.keys() else None,
            )

        return None

    @staticmethod
    def __adoe_cloner_factory(
        api_session: APISession,
        config_path: str,
        config_dict: Dict,
        ssl_no_verify: bool,
    ) -> Cloner:
        if CxOneFlowConfig.__has_basic_auth(config_dict):
            return Cloner.using_basic_auth(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
                ssl_no_verify,
                True,
            )

        if CxOneFlowConfig.__has_token_auth(config_dict):
            return Cloner.using_basic_auth(
                "",
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                ),
                ssl_no_verify,
                True,
            )

        if CxOneFlowConfig.__has_ssh_auth(config_dict):
            return Cloner.using_ssh_auth(
                Path(CxOneFlowConfig._secret_root)
                / Path(
                    CxOneFlowConfig._get_value_for_key_or_fail(
                        config_path, "ssh", config_dict
                    )
                ),
                config_dict["ssh-port"] if "ssh-port" in config_dict.keys() else None,
            )

        return None

    @staticmethod
    def __gh_cloner_factory(
        api_session: APISession,
        config_path: str,
        config_dict: Dict,
        ssl_no_verify: bool,
    ) -> Cloner:
        if CxOneFlowConfig.__has_basic_auth(config_dict):
            return Cloner.using_basic_auth(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
                ssl_no_verify,
                True,
            )

        if CxOneFlowConfig.__has_token_auth(config_dict):
            return Cloner.using_basic_auth(
                "git",
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                ),
                ssl_no_verify,
            )

        if CxOneFlowConfig.__has_ssh_auth(config_dict):
            return Cloner.using_ssh_auth(
                Path(CxOneFlowConfig._secret_root)
                / Path(
                    CxOneFlowConfig._get_value_for_key_or_fail(
                        config_path, "ssh", config_dict
                    )
                ),
                config_dict["ssh-port"] if "ssh-port" in config_dict.keys() else None,
            )

        if "app-private-key" in config_dict.keys():
            return Cloner.using_github_app_auth(
                GithubAppAuthFactory(
                    CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                        config_path, "app-private-key", config_dict
                    ),
                    api_session.api_endpoint,
                ),
                ssl_no_verify,
            )
        

    @staticmethod
    def __gl_cloner_factory(
        api_session: APISession,
        config_path: str,
        config_dict: Dict,
        ssl_no_verify: bool,
    ) -> Cloner:
        if CxOneFlowConfig.__has_basic_auth(config_dict):
            return Cloner.using_basic_auth(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
                ssl_no_verify,
                True,
            )

        if CxOneFlowConfig.__has_token_auth(config_dict):
            return Cloner.using_basic_auth("git", 
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                ),
                ssl_no_verify,
            )

        if CxOneFlowConfig.__has_ssh_auth(config_dict):
            return Cloner.using_ssh_auth(
                Path(CxOneFlowConfig._secret_root)
                / Path(
                    CxOneFlowConfig._get_value_for_key_or_fail(
                        config_path, "ssh", config_dict
                    )
                ),
                config_dict["ssh-port"] if "ssh-port" in config_dict.keys() else None,
            )

        return None

    @staticmethod
    def __adoe_api_auth_factory(
        api_url: str, config_path: str, config_dict: Dict
    ) -> AuthFactory:
        if CxOneFlowConfig.__has_token_auth(config_dict):
            return auth_basic(
                "",
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                ),
            )
        elif CxOneFlowConfig.__has_basic_auth(config_dict):
            return auth_basic(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
            )

        return None

    @staticmethod
    def __common_api_auth_factory(
        api_url: str, config_path: str, config_dict: Dict
    ) -> Union[AuthFactory, None]:
        if CxOneFlowConfig.__has_token_auth(config_dict):
            return auth_bearer(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "token", config_dict
                )
            )
        elif CxOneFlowConfig.__has_basic_auth(config_dict):
            return auth_basic(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "username", config_dict
                ),
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "password", config_dict
                ),
            )
        else:
            return None

    @staticmethod
    def __github_api_auth_factory(
        api_url: str, config_path: str, config_dict: Dict
    ) -> AuthFactory:
        common = CxOneFlowConfig.__common_api_auth_factory(api_url, config_path, config_dict)

        if (
            common is None
            and "app-private-key" in config_dict.keys()
            and config_dict["app-private-key"] is not None
        ):
            return GithubAppAuthFactory(
                CxOneFlowConfig._get_secret_from_value_of_key_or_fail(
                    config_path, "app-private-key", config_dict
                ),
                api_url,
            )
        return common

    __cloner_factories = {
        "bbdc": __bbdc_cloner_factory,
        "adoe": __adoe_cloner_factory,
        "gh": __gh_cloner_factory,
        "gl": __gl_cloner_factory,
    }

    __api_auth_factories = {
        "bbdc": __common_api_auth_factory,
        "adoe": __adoe_api_auth_factory,
        "gh": __github_api_auth_factory,
        "gl": __common_api_auth_factory,
    }

    __scm_factories = {
        "bbdc": BBDCService,
        "adoe": ADOEService,
        "gh": GHService,
        "gl": GLService,
    }
