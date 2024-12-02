from _version import __version__
from _agent import __agent__
from pathlib import Path
import re
import yaml, logging, cxone_api as cx, os
from scm_services import SCMService, ADOEService, BBDCService, GHService
from scm_services.cloner import Cloner
from api_utils import auth_basic, auth_bearer
from api_utils.apisession import APISession
from api_utils.auth_factories import AuthFactory, GithubAppAuthFactory
from cxone_service import CxOneService
from password_strength import PasswordPolicy
from cxoneflow_logging import SecretRegistry
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService
from workflows.pull_request import PullRequestWorkflow
from workflows.resolver_workflow import DummyResolverScanningWorkflow, ResolverScanningWorkflow
from workflows import ResultSeverity, ResultStates
from typing import Tuple, List
from multiprocessing import cpu_count
from typing import Dict, List, Union
from services import CxOneFlowServices


def get_workers_count():
    if "CXONEFLOW_WORKERS" not in os.environ.keys():
        return int(cpu_count() / 2)
    else:
        return min(int(cpu_count() - 1), int(os.environ['CXONEFLOW_WORKERS']))

def get_log_level():
    if "LOG_LEVEL" not in os.environ.keys():
        loglevel="INFO"
    else:
        loglevel=os.environ['LOG_LEVEL']


def get_config_path():
    if "CONFIG_YAML_PATH" in os.environ.keys():
        return os.environ['CONFIG_YAML_PATH']
    else:
        return "./config.yaml"


class ConfigurationException(Exception):

    @staticmethod
    def missing_key_path(key_path):
        return ConfigurationException(f"Missing key at path: {key_path}")

    @staticmethod
    def secret_load_error(key_path):
        return ConfigurationException(f"Could not load secret defined at: {key_path}")

    @staticmethod
    def invalid_value (key_path):
        return ConfigurationException(f"The value configured at {key_path} is invalid")

    @staticmethod
    def missing_keys(key_path, keys):
        return ConfigurationException(f"One or more of these elements are missing: {["/".join([key_path, x]) for x in keys]}")

    @staticmethod
    def missing_at_least_one_key_path(key_path, keys):
        return ConfigurationException(f"At least one of these elements is required: {["/".join([key_path, x]) for x in keys]}")

    @staticmethod
    def mutually_exclusive(key_path, keys):
        report_list = []
        for k in keys:
            if isinstance(k, str):
                report_list.append("/".join([key_path, k]))
            
            if isinstance(k, Tuple) or isinstance(k, List):
                report_list.append(f"{key_path}/({",".join(k)})")


        return ConfigurationException(f"Only one should be defined: {report_list}")

    @staticmethod
    def key_mismatch(key_path, provided, needed):
        return ConfigurationException(f"{key_path} invalid: Needed {needed} but provided {provided}.")

    @staticmethod
    def invalid_keys(key_path, keys : List):
        return ConfigurationException(f"These keys are invalid: {["/".join([key_path, x]) for x in keys]}")

class RouteNotFoundException(Exception):
    pass

class CxOneFlowConfig:
    __shared_secret_policy = PasswordPolicy.from_names(length=20, uppercase=3, numbers=3, special=2)

    @staticmethod
    def log():
        return logging.getLogger("CxOneFlowConfig")

    @staticmethod
    def get_default_ssl_verify_value():
        if 'REQUESTS_CA_BUNDLE' in os.environ.keys():
            return os.environ['REQUESTS_CA_BUNDLE']
        
        default_paths = [
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt"
        ]
        for bundle in default_paths:
            if os.path.exists(bundle):
                return bundle

        CxOneFlowConfig.log().warning("************SSL verification is turned OFF************")
        CxOneFlowConfig.log().warning("A path to the default CA bundle could not be determined.  Please set the REQUESTS_CA_BUNDLE environment variable.")
        return False
   
    
    
    @staticmethod
    def get_service_monikers():
        return list(CxOneFlowConfig.__scm_services_config_by_service_moniker.keys())

    @staticmethod
    def retrieve_services_by_moniker(moniker : str) -> CxOneFlowServices:
        return CxOneFlowConfig.__scm_services_config_by_service_moniker[moniker]


    @staticmethod
    def retrieve_scm_services(scm_config_key : str) -> List[SCMService]:
        return [entry.scm for entry in CxOneFlowConfig.__ordered_scm_services_config[scm_config_key]]

    @staticmethod
    def retrieve_services_by_route(clone_urls : str, scm_config_key : str) -> CxOneFlowServices:
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
    def bootstrap(config_file_path = "./config.yaml"):

        try:
            CxOneFlowConfig.log().info(f"Loading configuration from {config_file_path}")

            with open(config_file_path, "rt") as cfg:
                CxOneFlowConfig.__raw = yaml.safe_load(cfg)

            CxOneFlowConfig.__server_base_url = CxOneFlowConfig.__get_value_for_key_or_fail("", "server-base-url", CxOneFlowConfig.__raw)
            CxOneFlowConfig.__secret_root = CxOneFlowConfig.__get_value_for_key_or_fail("", "secret-root-path", CxOneFlowConfig.__raw)

            if len(CxOneFlowConfig.__raw.keys() - CxOneFlowConfig.__cloner_factories.keys()) == len(CxOneFlowConfig.__raw.keys()):
                raise ConfigurationException.missing_at_least_one_key_path("/", CxOneFlowConfig.__cloner_factories.keys())
            
            for scm in CxOneFlowConfig.__cloner_factories.keys():

                if scm in CxOneFlowConfig.__raw.keys():
                    index = 0
                    for repo_config_dict in CxOneFlowConfig.__raw[scm]:

                        services = CxOneFlowConfig.__setup_scm(CxOneFlowConfig.__cloner_factories[scm], 
                                CxOneFlowConfig.__auth_factories[scm], 
                                CxOneFlowConfig.__scm_factories[scm],
                                repo_config_dict, f"/{scm}[{index}]")
                        
                        if services.scm.moniker not in CxOneFlowConfig.__scm_services_config_by_service_moniker.keys():
                            CxOneFlowConfig.__scm_services_config_by_service_moniker[services.scm.moniker] = services
                        else:
                             raise ConfigurationException(f"Service {services.scm.moniker} is defined more than once.")
						
                        if not scm in CxOneFlowConfig.__ordered_scm_services_config:
                            CxOneFlowConfig.__ordered_scm_services_config[scm] = [services]
                        else:
                            CxOneFlowConfig.__ordered_scm_services_config[scm].append(services)

                        index += 1
        except Exception as ex:
            CxOneFlowConfig.log().exception(ex)
            raise
    

    @staticmethod
    def __get_value_for_key_or_fail(config_path, key, config_dict):
        if not key in config_dict.keys():
            raise ConfigurationException.missing_key_path(f"{config_path}/{key}")
        else:
            return config_dict[key]

    @staticmethod
    def __get_file_contents_from_value_of_key_or_default(config_dict, key, default):
        if not key in config_dict.keys():
            return default
        else:
            if not os.path.isfile(Path(CxOneFlowConfig.__secret_root) / Path(config_dict[key])):
                return default
            else:
                with open(Path(CxOneFlowConfig.__secret_root) / Path(config_dict[key]), "rt") as f:
                    return f.read().strip()


    @staticmethod
    def __get_secret_from_value_of_key_or_default(config_dict, key, default):
        return SecretRegistry.register(CxOneFlowConfig.__get_file_contents_from_value_of_key_or_default(config_dict, key, default))

    @staticmethod
    def __get_secret_from_value_of_key_or_fail(config_path, key, config_dict):
        retval = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(config_dict, key, None)

        if retval is None:
            raise ConfigurationException.secret_load_error(f"{config_path}/{key}")
        
        return retval


    @staticmethod
    def __get_value_for_key_or_default(key, config_dict, default):
        if config_dict is None or not key in config_dict.keys():
            return default
        else:
            return config_dict[key]


    __default_amqp_url = "amqp://localhost:5672"


    @staticmethod
    def __load_amqp_settings(config_path, **kwargs) -> Union[str, str, str, bool]:
        amqp_dict = CxOneFlowConfig.__get_value_for_key_or_default("amqp", kwargs, None)
        if not amqp_dict is None:
            amqp_url = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, "amqp-url", amqp_dict)
            amqp_user = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(amqp_dict, "amqp-user", None)
            amqp_password = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(amqp_dict, "amqp-password", None)
            ssl_verify = CxOneFlowConfig.__get_value_for_key_or_default("ssl-verify", amqp_dict, CxOneFlowConfig.get_default_ssl_verify_value())
            return amqp_url, amqp_user, amqp_password, ssl_verify
        else:
            return CxOneFlowConfig.__default_amqp_url, None, None, True
       

    @staticmethod
    def __resolver_service_factory(config_path, moniker, **kwargs) -> ResolverScanService:
         if kwargs is None or len(kwargs) == 0:
            return ResolverScanService(moniker, CxOneFlowConfig.__default_amqp_url, None, None, DummyResolverScanningWorkflow(), 
                                       False, None, None, None, None)
         else:
            msg_signing_key = CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "private-key", kwargs)
            
            emit_resolver_logs = CxOneFlowConfig.__get_value_for_key_or_default("emit-resolver-logs", kwargs, False)
                
            
            default_tag = CxOneFlowConfig.__get_value_for_key_or_default("default-agent-tag", kwargs, None)
            project_tag_key = CxOneFlowConfig.__get_value_for_key_or_default("resolver-tag-key", kwargs, "resolver")
            no_container_tag_list = CxOneFlowConfig.__get_value_for_key_or_default("agent-tags", kwargs, [])
            container_agent_tag_dict = CxOneFlowConfig.__get_value_for_key_or_default("container-agent-tags", kwargs, {})

            # Make sure tags are not duplicate
            tag_intersection = list(set(no_container_tag_list) & set(list(container_agent_tag_dict.keys())))
            if len(tag_intersection) > 0:
                 raise ConfigurationException(f"{config_path} contains duplicate resolver tags {tag_intersection}")
                 
                    
            # the default tag must have a tag.
            if default_tag is not None and not default_tag in no_container_tag_list + list(container_agent_tag_dict.keys()):
                raise ConfigurationException.missing_keys(f"{config_path}/agent-tags or {config_path}/container-agent-tags", [default_tag])

            amqp_url, amqp_user, amqp_password, ssl_verify = CxOneFlowConfig.__load_amqp_settings(config_path, **kwargs)
           
            return ResolverScanService(moniker, amqp_url, amqp_user, amqp_password, ssl_verify, 
                                       ResolverScanningWorkflow(emit_resolver_logs, msg_signing_key), 
                                       default_tag, project_tag_key, container_agent_tag_dict, no_container_tag_list)

    

    @staticmethod
    def __pr_feedback_service_factory(config_path, moniker, **kwargs) -> PRFeedbackService:
        if kwargs is None or len(kwargs.keys()) == 0:
            return PRFeedbackService(moniker, CxOneFlowConfig.__default_amqp_url, None, None, True, CxOneFlowConfig.__server_base_url, 
                                        PullRequestWorkflow())
        else:

            pr_workflow_dict = CxOneFlowConfig.__get_value_for_key_or_default("pull-request", kwargs, {})
            scan_monitor_dict = CxOneFlowConfig.__get_value_for_key_or_default("scan-monitor", kwargs, {})

            exclusions_dict = CxOneFlowConfig.__get_value_for_key_or_default("exclusions", kwargs, {})
            excluded_states = excluded_severities = []

            try:
                excluded_states = [ResultStates(state) for state in CxOneFlowConfig.__get_value_for_key_or_default("state", exclusions_dict, [])]
            except ValueError as ve:
                raise ConfigurationException(f"{config_path}/exclusions/state {ve}: must be one of {ResultStates.names()}")

            try:
                excluded_severities = [ResultSeverity(sev) for sev in CxOneFlowConfig.__get_value_for_key_or_default("severity", exclusions_dict, [])]
            except ValueError as ve:
                raise ConfigurationException(f"{config_path}/exclusions/severity {ve}: must be one of {ResultSeverity.names()}")

            pr_workflow = PullRequestWorkflow(excluded_severities, excluded_states,
                CxOneFlowConfig.__get_value_for_key_or_default("enabled", pr_workflow_dict, False), \
                int(CxOneFlowConfig.__get_value_for_key_or_default("poll-interval-seconds", scan_monitor_dict, 60)), \
                int(CxOneFlowConfig.__get_value_for_key_or_default("scan-timeout-hours", scan_monitor_dict, 48)) \
                )

            max_poll_interval = int(CxOneFlowConfig.__get_value_for_key_or_default("poll-max-interval-seconds", scan_monitor_dict, 600))
            poll_backoff = int(CxOneFlowConfig.__get_value_for_key_or_default("poll-backoff-multiplier", scan_monitor_dict, 2))

            amqp_url, amqp_user, amqp_password, ssl_verify = CxOneFlowConfig.__load_amqp_settings(config_path, **kwargs)

            return PRFeedbackService(moniker, amqp_url, amqp_user, amqp_password, ssl_verify, CxOneFlowConfig.__server_base_url, pr_workflow, \
                                        max_poll_interval, poll_backoff)

            

    @staticmethod
    def __cxone_client_factory(config_path, **kwargs):

        always_required = ['tenant', 'iam-endpoint', 'api-endpoint']

        if len(always_required - kwargs.keys()) != 0:
            raise ConfigurationException.missing_keys(config_path, always_required)

        one_required = ['api-key','oauth']
        one_found = len([x for x in one_required if x in kwargs.keys()])

        if one_found != 1:
            raise ConfigurationException.mutually_exclusive(config_path, one_required)
        

        tenant_name = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'tenant', kwargs)

        iam_endpoint_value = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'iam-endpoint', kwargs)
        tenant_auth_endpoint = None
        if iam_endpoint_value in cx.AuthRegionEndpoints.keys():
            tenant_auth_endpoint = cx.AuthRegionEndpoints[iam_endpoint_value](tenant_name)
        else:
            tenant_auth_endpoint = cx.CxOneAuthEndpoint(tenant_name, iam_endpoint_value)


        api_endpoint_value = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'api-endpoint', kwargs)
        tenant_api_endpoint = None
        if api_endpoint_value in cx.ApiRegionEndpoints.keys():
            tenant_api_endpoint = cx.ApiRegionEndpoints[api_endpoint_value]()
        else:
            tenant_api_endpoint = cx.CxOneApiEndpoint(api_endpoint_value)

        if 'api-key' in kwargs.keys():
            return cx.CxOneClient.create_with_api_key(
                CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, 'api-key', kwargs), \
                __agent__, \
                tenant_auth_endpoint, \
                tenant_api_endpoint, \
                CxOneFlowConfig.__get_value_for_key_or_default('timeout-seconds', kwargs, 60), \
                CxOneFlowConfig.__get_value_for_key_or_default('retries', kwargs, 3), \
                CxOneFlowConfig.__get_value_for_key_or_default('proxies', kwargs, None), \
                CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', kwargs, CxOneFlowConfig.get_default_ssl_verify_value()) \
                )
        elif 'oauth' in kwargs.keys():
            oauth_params = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'oauth', kwargs)
            oauth_id = CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(f"{config_path}/oauth", 'client-id', oauth_params)
            oauth_secret = CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(f"{config_path}/oauth", 'client-secret', oauth_params)

            return cx.CxOneClient.create_with_oauth(
                oauth_id, oauth_secret, \
                __agent__, \
                tenant_auth_endpoint, \
                tenant_api_endpoint, \
                CxOneFlowConfig.__get_value_for_key_or_default('timeout-seconds', kwargs, 60), \
                CxOneFlowConfig.__get_value_for_key_or_default('retries', kwargs, 3), \
                CxOneFlowConfig.__get_value_for_key_or_default('proxies', kwargs, None), \
                CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', kwargs, CxOneFlowConfig.get_default_ssl_verify_value()) \
                )

        return None


    __ordered_scm_services_config = {}
    __scm_services_config_by_service_moniker = {}

    @staticmethod
    def __scm_api_auth_factory(api_url : str, api_auth_factory, config_dict, config_path):
        retval = None

        if config_dict is not None and len(config_dict.keys()) > 0:

            retval = api_auth_factory(api_url, config_path, config_dict)

        if retval is None:
            raise ConfigurationException(f"{config_path} SCM API authorization configuration is invalid!")
        
        return retval


    @staticmethod
    def __cloner_factory(api_session : APISession, scm_cloner_factory, clone_auth_dict, config_path):

        retval = scm_cloner_factory(api_session, Path(CxOneFlowConfig.__secret_root), clone_auth_dict)

        if retval is None:
            raise ConfigurationException(f"{config_path} SCM clone authorization configuration is invalid!")
        
        return retval

    @staticmethod
    def __setup_scm(cloner_factory, api_auth_factory, scm_class, config_dict, config_path) -> CxOneFlowServices:
        repo_matcher = re.compile(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'repo-match', config_dict), re.IGNORECASE)

        service_moniker = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'service-name', config_dict)

        cxone_client = CxOneFlowConfig.__cxone_client_factory(f"{config_path}/cxone", 
                                                            **(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'cxone', config_dict)))
        
        pr_feedback_service = CxOneFlowConfig.__pr_feedback_service_factory(f"{config_path}/feedback", service_moniker, 
                                                                **(CxOneFlowConfig.__get_value_for_key_or_default('feedback', config_dict, {})))
        
        resolver_service = CxOneFlowConfig.__resolver_service_factory(f"{config_path}/resolver", service_moniker, 
                                                                **(CxOneFlowConfig.__get_value_for_key_or_default('resolver', config_dict, {})))

        scan_config_dict = CxOneFlowConfig.__get_value_for_key_or_default('scan-config', config_dict, {} )

        cxone_service = CxOneService(service_moniker, cxone_client, \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-scan-engines', scan_config_dict, {}), \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-scan-tags', scan_config_dict, {}), \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-project-tags', scan_config_dict, {}), \
                                     )

        connection_config_dict = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'connection', config_dict)


        api_auth_dict = CxOneFlowConfig.__get_value_for_key_or_fail(f"{config_path}/connection", 'api-auth', connection_config_dict)


        api_base_url = CxOneFlowConfig.__get_value_for_key_or_fail(f"{config_path}/connection", 'base-url', connection_config_dict)

        display_url = CxOneFlowConfig.__get_value_for_key_or_default('base-display-url', connection_config_dict, api_base_url)

        api_url = APISession.form_api_endpoint(api_base_url,
                                               CxOneFlowConfig.__get_value_for_key_or_default('api-url-suffix', connection_config_dict, None))

        api_session = APISession(api_url, \
                                 CxOneFlowConfig.__scm_api_auth_factory(api_url, api_auth_factory, api_auth_dict, f"{config_path}/connection/api-auth"), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('timeout-seconds', connection_config_dict, 60), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('retries', connection_config_dict, 3), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('proxies', connection_config_dict, None), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', connection_config_dict, 
                                 CxOneFlowConfig.get_default_ssl_verify_value()))
        
        scm_shared_secret = CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(f"{config_path}/connection", 'shared-secret', connection_config_dict)
        secret_test_result = CxOneFlowConfig.__shared_secret_policy.test(scm_shared_secret)
        if not len(secret_test_result) == 0:
            raise ConfigurationException(f"{config_path}/connection/shared-secret fails some complexity requirements: {secret_test_result}")
        
        clone_auth_dict = CxOneFlowConfig.__get_value_for_key_or_default('clone-auth', connection_config_dict, None)
        clone_config_path = f"{config_path}/connection/clone-auth"
        if clone_auth_dict is None:
            clone_auth_dict = api_auth_dict
            clone_config_path = f"{config_path}/connection/api-auth"
               
        scm_service = scm_class(display_url, service_moniker, api_session, scm_shared_secret, 
                                CxOneFlowConfig.__cloner_factory(api_session, cloner_factory, clone_auth_dict, clone_config_path))

        return CxOneFlowServices(repo_matcher, cxone_service, scm_service, pr_feedback_service, resolver_service)

    @staticmethod
    def __has_basic_auth(config_dict : Dict) -> bool:
            if 'username' in config_dict.keys() and 'password' in config_dict.keys():
                    if config_dict['username'] is not None and config_dict['password'] is not None:
                            return True
            return False

    @staticmethod
    def __has_token_auth(config_dict : Dict) -> bool:
            if 'token' in config_dict.keys():
                    if config_dict['token'] is not None:
                            return True
            return False

    @staticmethod
    def __has_ssh_auth(config_dict : Dict) -> bool:
            if 'ssh' in config_dict.keys():
                    if config_dict['ssh'] is not None:
                            return True
            return False


    @staticmethod
    def __bitbucketdc_cloner_factory(api_session : APISession, config_path : str, config_dict : Dict) -> Cloner:
            if CxOneFlowConfig.__has_basic_auth(config_dict):
                    return Cloner.using_basic_auth(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 

            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_token_auth(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig.__secret_root) / 
                            Path(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)

            return None        

    @staticmethod
    def __adoe_cloner_factory(api_session : APISession, config_path : str, config_dict : Dict) -> Cloner:
            if CxOneFlowConfig.__has_basic_auth(config_dict):
                    return Cloner.using_basic_auth(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 
            
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_basic_auth("", CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict), True)

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig.__secret_root) / 
                            Path(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)
            
            CxOneFlowConfig.__get_value_for_key_or_fail

            return None        

    @staticmethod
    def __gh_cloner_factory(api_session : APISession, config_path : str, config_dict : Dict) -> Cloner:
            if CxOneFlowConfig.__has_basic_auth(config_dict):
                    return Cloner.using_basic_auth(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 

            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_basic_auth("git", CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig.__secret_root) / 
                            Path(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)

            if 'app-private-key' in config_dict.keys():
                return Cloner.using_github_app_auth(GithubAppAuthFactory
                    (CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "app-private-key", config_dict), api_session.api_endpoint))


    @staticmethod
    def __adoe_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_basic("", CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))
            
            return None


    @staticmethod
    def __bbdc_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_bearer(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))

            return None

    @staticmethod
    def __github_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_bearer(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))
            elif 'app-private-key' in config_dict.keys() and config_dict['app-private-key'] is not None:
                    return GithubAppAuthFactory(CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(config_path, "app-private-key", config_dict), 
                                                api_url)

            return None


    __cloner_factories = {
        'bbdc' : __bitbucketdc_cloner_factory,
        'adoe' : __adoe_cloner_factory,
        'gh' : __gh_cloner_factory
        }

    __auth_factories = {
        'bbdc' : __bbdc_api_auth_factory,
        'adoe' : __adoe_api_auth_factory,
        'gh' : __github_api_auth_factory
        }
        
    __scm_factories = {
        'bbdc' : BBDCService,
        'adoe' : ADOEService,
        'gh' : GHService
        }

