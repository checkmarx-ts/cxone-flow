from _version import __version__
from _agent import __agent__
from pathlib import Path
from .. import ConfigurationException, RouteNotFoundException, CommonConfig
import re, yaml
from scm_services import SCMService, ADOEService, BBDCService, GHService
from scm_services.cloner import Cloner
from api_utils import auth_basic, auth_bearer
from api_utils.apisession import APISession
from api_utils.auth_factories import AuthFactory, GithubAppAuthFactory
from cxone_service import CxOneService
from password_strength import PasswordPolicy
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService
from workflows.pull_request import PullRequestWorkflow
from workflows.resolver_workflow import DummyResolverScanningWorkflow, ResolverScanningWorkflow
from workflows import ResultSeverity, ResultStates
from services import CxOneFlowServices
from typing import List, Dict

class CxOneFlowConfig(CommonConfig):
    __shared_secret_policy = PasswordPolicy.from_names(length=20, uppercase=3, numbers=3, special=2)

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
                raw_yaml = yaml.safe_load(cfg)

            CxOneFlowConfig.__server_base_url = CxOneFlowConfig._get_value_for_key_or_fail("", "server-base-url", raw_yaml)
            CommonConfig._secret_root = CxOneFlowConfig._get_value_for_key_or_fail("", "secret-root-path", raw_yaml)

            if len(raw_yaml.keys() - CxOneFlowConfig.__cloner_factories.keys()) == len(raw_yaml.keys()):
                raise ConfigurationException.missing_at_least_one_key_path("/", CxOneFlowConfig.__cloner_factories.keys())
            
            for scm in CxOneFlowConfig.__cloner_factories.keys():

                if scm in raw_yaml.keys():
                    index = 0
                    for repo_config_dict in raw_yaml[scm]:

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
    def __resolver_service_factory(config_path, moniker, **kwargs) -> ResolverScanService:
         if kwargs is None or len(kwargs) == 0:
            return ResolverScanService(moniker, CommonConfig._default_amqp_url, None, None, DummyResolverScanningWorkflow(), 
                                       False, None, None, None, None)
         else:
            msg_private_key = CxOneFlowConfig._get_secret_from_value_of_key_or_fail(f"{config_path}/payload-signature", "private-key", kwargs)
            
            emit_resolver_logs = CxOneFlowConfig._get_value_for_key_or_default("emit-resolver-logs", kwargs, False)
            
            default_tag = CxOneFlowConfig._get_value_for_key_or_default("default-agent-tag", kwargs, None)
            project_tag_key = CxOneFlowConfig._get_value_for_key_or_default("resolver-tag-key", kwargs, "resolver")
            no_container_tag_list = CxOneFlowConfig._get_value_for_key_or_default("agent-tags", kwargs, [])
            container_agent_tag_dict = CxOneFlowConfig._get_value_for_key_or_default("container-agent-tags", kwargs, {})

            # Make sure tags are not duplicate
            tag_intersection = list(set(no_container_tag_list) & set(list(container_agent_tag_dict.keys())))
            if len(tag_intersection) > 0:
                 raise ConfigurationException(f"{config_path} contains duplicate resolver tags {tag_intersection}")
                 
                    
            # the default tag must have a tag.
            if default_tag is not None and not default_tag in no_container_tag_list + list(container_agent_tag_dict.keys()):
                raise ConfigurationException.missing_keys(f"{config_path}/agent-tags or {config_path}/container-agent-tags", [default_tag])

            amqp_url, amqp_user, amqp_password, ssl_verify = CxOneFlowConfig._load_amqp_settings(config_path, **kwargs)
           
            return ResolverScanService(moniker, amqp_url, amqp_user, amqp_password, ssl_verify, 
                                       ResolverScanningWorkflow.from_private_key(emit_resolver_logs, bytes(msg_private_key, "UTF-8")), 
                                       default_tag, project_tag_key, container_agent_tag_dict, no_container_tag_list)

    

    @staticmethod
    def __pr_feedback_service_factory(config_path, moniker, **kwargs) -> PRFeedbackService:
        if kwargs is None or len(kwargs.keys()) == 0:
            return PRFeedbackService(moniker, CxOneFlowConfig._default_amqp_url, None, None, True, CxOneFlowConfig.__server_base_url, 
                                        PullRequestWorkflow())
        else:

            pr_workflow_dict = CxOneFlowConfig._get_value_for_key_or_default("pull-request", kwargs, {})
            scan_monitor_dict = CxOneFlowConfig._get_value_for_key_or_default("scan-monitor", kwargs, {})

            exclusions_dict = CxOneFlowConfig._get_value_for_key_or_default("exclusions", kwargs, {})
            excluded_states = excluded_severities = []

            try:
                excluded_states = [ResultStates(state) for state in CxOneFlowConfig._get_value_for_key_or_default("state", exclusions_dict, [])]
            except ValueError as ve:
                raise ConfigurationException(f"{config_path}/exclusions/state {ve}: must be one of {ResultStates.names()}")

            try:
                excluded_severities = [ResultSeverity(sev) for sev in CxOneFlowConfig._get_value_for_key_or_default("severity", exclusions_dict, [])]
            except ValueError as ve:
                raise ConfigurationException(f"{config_path}/exclusions/severity {ve}: must be one of {ResultSeverity.names()}")

            pr_workflow = PullRequestWorkflow(excluded_severities, excluded_states,
                CxOneFlowConfig._get_value_for_key_or_default("enabled", pr_workflow_dict, False), \
                int(CxOneFlowConfig._get_value_for_key_or_default("poll-interval-seconds", scan_monitor_dict, 60)), \
                int(CxOneFlowConfig._get_value_for_key_or_default("scan-timeout-hours", scan_monitor_dict, 48)) \
                )

            max_poll_interval = int(CxOneFlowConfig._get_value_for_key_or_default("poll-max-interval-seconds", scan_monitor_dict, 600))
            poll_backoff = int(CxOneFlowConfig._get_value_for_key_or_default("poll-backoff-multiplier", scan_monitor_dict, 2))

            amqp_url, amqp_user, amqp_password, ssl_verify = CxOneFlowConfig._load_amqp_settings(config_path, **kwargs)

            return PRFeedbackService(moniker, amqp_url, amqp_user, amqp_password, ssl_verify, CxOneFlowConfig.__server_base_url, pr_workflow, \
                                        max_poll_interval, poll_backoff)

            
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

        retval = scm_cloner_factory(api_session, Path(CxOneFlowConfig._secret_root), clone_auth_dict)

        if retval is None:
            raise ConfigurationException(f"{config_path} SCM clone authorization configuration is invalid!")
        
        return retval

    @staticmethod
    def __setup_scm(cloner_factory, api_auth_factory, scm_class, config_dict, config_path) -> CxOneFlowServices:
        repo_matcher = re.compile(CxOneFlowConfig._get_value_for_key_or_fail(config_path, 'repo-match', config_dict), re.IGNORECASE)

        service_moniker = CxOneFlowConfig._get_value_for_key_or_fail(config_path, 'service-name', config_dict)

        cxone_client = CxOneFlowConfig._cxone_client_factory(f"{config_path}/cxone", 
                                                            **(CxOneFlowConfig._get_value_for_key_or_fail(config_path, 'cxone', config_dict)))
        
        pr_feedback_service = CxOneFlowConfig.__pr_feedback_service_factory(f"{config_path}/feedback", service_moniker, 
                                                                **(CxOneFlowConfig._get_value_for_key_or_default('feedback', config_dict, {})))
        
        resolver_service = CxOneFlowConfig.__resolver_service_factory(f"{config_path}/resolver", service_moniker, 
                                                                **(CxOneFlowConfig._get_value_for_key_or_default('resolver', config_dict, {})))

        scan_config_dict = CxOneFlowConfig._get_value_for_key_or_default('scan-config', config_dict, {} )

        cxone_service = CxOneService(service_moniker, cxone_client, \
                                     CxOneFlowConfig._get_value_for_key_or_default('default-scan-engines', scan_config_dict, {}), \
                                     CxOneFlowConfig._get_value_for_key_or_default('default-scan-tags', scan_config_dict, {}), \
                                     CxOneFlowConfig._get_value_for_key_or_default('default-project-tags', scan_config_dict, {}), \
                                     )

        connection_config_dict = CxOneFlowConfig._get_value_for_key_or_fail(config_path, 'connection', config_dict)


        api_auth_dict = CxOneFlowConfig._get_value_for_key_or_fail(f"{config_path}/connection", 'api-auth', connection_config_dict)


        api_base_url = CxOneFlowConfig._get_value_for_key_or_fail(f"{config_path}/connection", 'base-url', connection_config_dict)

        display_url = CxOneFlowConfig._get_value_for_key_or_default('base-display-url', connection_config_dict, api_base_url)

        api_url = APISession.form_api_endpoint(api_base_url,
                                               CxOneFlowConfig._get_value_for_key_or_default('api-url-suffix', connection_config_dict, None))

        api_session = APISession(api_url, \
                                 CxOneFlowConfig.__scm_api_auth_factory(api_url, api_auth_factory, api_auth_dict, f"{config_path}/connection/api-auth"), \
                                 CxOneFlowConfig._get_value_for_key_or_default('timeout-seconds', connection_config_dict, 60), \
                                 CxOneFlowConfig._get_value_for_key_or_default('retries', connection_config_dict, 3), \
                                 CxOneFlowConfig._get_value_for_key_or_default('proxies', connection_config_dict, None), \
                                 CxOneFlowConfig._get_value_for_key_or_default('ssl-verify', connection_config_dict, 
                                 CxOneFlowConfig.get_default_ssl_verify_value()))
        
        scm_shared_secret = CxOneFlowConfig._get_secret_from_value_of_key_or_fail(f"{config_path}/connection", 'shared-secret', connection_config_dict)
        secret_test_result = CxOneFlowConfig.__shared_secret_policy.test(scm_shared_secret)
        if not len(secret_test_result) == 0:
            raise ConfigurationException(f"{config_path}/connection/shared-secret fails some complexity requirements: {secret_test_result}")
        
        clone_auth_dict = CxOneFlowConfig._get_value_for_key_or_default('clone-auth', connection_config_dict, None)
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
                    return Cloner.using_basic_auth(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 

            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_token_auth(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig._secret_root) / 
                            Path(CxOneFlowConfig._get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)

            return None        

    @staticmethod
    def __adoe_cloner_factory(api_session : APISession, config_path : str, config_dict : Dict) -> Cloner:
            if CxOneFlowConfig.__has_basic_auth(config_dict):
                    return Cloner.using_basic_auth(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 
            
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_basic_auth("", CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict), True)

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig._secret_root) / 
                            Path(CxOneFlowConfig._get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)
            
            CxOneFlowConfig._get_value_for_key_or_fail

            return None        

    @staticmethod
    def __gh_cloner_factory(api_session : APISession, config_path : str, config_dict : Dict) -> Cloner:
            if CxOneFlowConfig.__has_basic_auth(config_dict):
                    return Cloner.using_basic_auth(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict), True) 

            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return Cloner.using_basic_auth("git", CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))

            if CxOneFlowConfig.__has_ssh_auth(config_dict):
                    return Cloner.using_ssh_auth(Path(CxOneFlowConfig._secret_root) / 
                            Path(CxOneFlowConfig._get_value_for_key_or_fail(config_path, "ssh", config_dict)), 
                            config_dict['ssh-port'] if 'ssh-port' in config_dict.keys() else None)

            if 'app-private-key' in config_dict.keys():
                return Cloner.using_github_app_auth(GithubAppAuthFactory
                    (CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "app-private-key", config_dict), api_session.api_endpoint))


    @staticmethod
    def __adoe_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_basic("", CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))
            
            return None


    @staticmethod
    def __bbdc_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_bearer(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))

            return None

    @staticmethod
    def __github_api_auth_factory(api_url : str, config_path : str, config_dict : Dict) -> AuthFactory:
            if CxOneFlowConfig.__has_token_auth(config_dict):
                    return auth_bearer(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "token", config_dict))
            elif CxOneFlowConfig.__has_basic_auth(config_dict):
                    return auth_basic(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "username", config_dict), 
                        CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "password", config_dict))
            elif 'app-private-key' in config_dict.keys() and config_dict['app-private-key'] is not None:
                    return GithubAppAuthFactory(CxOneFlowConfig._get_secret_from_value_of_key_or_fail(config_path, "app-private-key", config_dict), 
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

