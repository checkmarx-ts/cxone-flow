from _version import __version__
from _agent import __agent__
from pathlib import Path
import re
import yaml, logging, cxone_api as cx, os
from scm_services import \
    bitbucketdc_cloner_factory, \
    adoe_cloner_factory, \
    adoe_api_auth_factory, \
    bbdc_api_auth_factory, \
    SCMService, ADOEService, BBDCService
from api_utils import APISession
from cxone_service import CxOneService
from password_strength import PasswordPolicy
from cxoneflow_logging import SecretRegistry
from workflows.state_service import WorkflowStateService
from workflows.pull_request import PullRequestWorkflow
from workflows import ResultSeverity, ResultStates
from typing import Tuple
from multiprocessing import cpu_count


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
        return ConfigurationException(f"Only one of these keys should be defined: {["/".join([key_path, x]) for x in keys]}")

    @staticmethod
    def invalid_keys(key_path, keys):
        return ConfigurationException(f"These keys are invalid: {["/".join([key_path, x]) for x in keys]}")

class RouteNotFoundException(Exception):
    pass

class CxOneFlowConfig:
    __shared_secret_policy = PasswordPolicy.from_names(length=20, uppercase=3, numbers=3, special=2)

    __cxone_service_tuple_index = 1
    __scm_service_tuple_index = 2
    __workflow_service_tuple_index = 3

    @staticmethod
    def log():
        return logging.getLogger("CxOneFlowConfig")
    
    @staticmethod
    def get_service_monikers():
        return list(CxOneFlowConfig.__scm_config_tuples_by_service_moniker.keys())

    @staticmethod
    def retrieve_services_by_moniker(moniker : str) -> Tuple[CxOneService,SCMService,WorkflowStateService]:
        service_tuple = CxOneFlowConfig.__scm_config_tuples_by_service_moniker[moniker]
        return service_tuple[CxOneFlowConfig.__cxone_service_tuple_index], service_tuple[CxOneFlowConfig.__scm_service_tuple_index], \
            service_tuple[CxOneFlowConfig.__workflow_service_tuple_index]


    @staticmethod
    def retrieve_services_by_route(clone_urls : str, scm_config_key : str) -> Tuple[CxOneService,SCMService,WorkflowStateService]:
        if type(clone_urls) is list:
            it_list = clone_urls
        else:
            it_list = [clone_urls]

        for url in it_list:
            for entry in CxOneFlowConfig.__ordered_scm_config_tuples[scm_config_key]:
                if entry[0].match(url):
                    return entry[CxOneFlowConfig.__cxone_service_tuple_index], entry[CxOneFlowConfig.__scm_service_tuple_index], \
                    entry[CxOneFlowConfig.__workflow_service_tuple_index]

        CxOneFlowConfig.log().error(f"No route matched for {clone_urls}")
        raise RouteNotFoundException(clone_urls)

    @staticmethod
    def bootstrap(config_file_path = "./config.yaml"):

        try:
            CxOneFlowConfig.log().info(f"Loading configuration from {config_file_path}")

            with open(config_file_path, "rt") as cfg:
                CxOneFlowConfig.__raw = yaml.safe_load(cfg)

            if not "secret-root-path" in CxOneFlowConfig.__raw.keys():
                raise ConfigurationException.missing_key_path("/secret-root-path")
            else:
                CxOneFlowConfig.__secret_root = CxOneFlowConfig.__raw['secret-root-path']

            if len(CxOneFlowConfig.__raw.keys() - CxOneFlowConfig.__cloner_factories.keys()) == len(CxOneFlowConfig.__raw.keys()):
                raise ConfigurationException.missing_at_least_one_key_path("/", CxOneFlowConfig.__cloner_factories.keys())
            
            for scm in CxOneFlowConfig.__cloner_factories.keys():

                if scm in CxOneFlowConfig.__raw.keys():
                    index = 0
                    for repo_config_dict in CxOneFlowConfig.__raw[scm]:

                        repo_matcher, cxone_service, scm_service, workflow_service_client = CxOneFlowConfig.__setup_scm(CxOneFlowConfig.__cloner_factories[scm], 
                                                                                               CxOneFlowConfig.__auth_factories[scm], 
                                                                                               CxOneFlowConfig.__scm_factories[scm],
                                                                                               repo_config_dict, f"/{scm}[{index}]")
                        
                        scm_tuple = (repo_matcher, cxone_service, scm_service, workflow_service_client)
                        CxOneFlowConfig.__scm_config_tuples_by_service_moniker[scm_service.moniker] = scm_tuple
						
                        if not scm in CxOneFlowConfig.__ordered_scm_config_tuples:
                            CxOneFlowConfig.__ordered_scm_config_tuples[scm] = [scm_tuple]
                        else:
                            CxOneFlowConfig.__ordered_scm_config_tuples[scm].append(scm_tuple)

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
    def __get_secret_from_value_of_key_or_default(config_dict, key, default):
        if not key in config_dict.keys():
            return SecretRegistry.register(default)
        else:
            if not os.path.isfile(Path(CxOneFlowConfig.__secret_root) / Path(config_dict[key])):
                return SecretRegistry.register(default)
            else:
                with open(Path(CxOneFlowConfig.__secret_root) / Path(config_dict[key]), "rt") as secret:
                    return SecretRegistry.register(secret.readline().strip())

    @staticmethod
    def __get_secret_from_value_of_key_or_fail(config_path, key, config_dict):
        retval = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(config_dict, key, None)

        if retval is None:
            raise ConfigurationException.secret_load_error(f"{config_path}/{key}")
        
        return retval


    @staticmethod
    def __get_value_for_key_or_default(key, config_dict, default):
        if not key in config_dict.keys():
            return default
        else:
            return config_dict[key]


    __default_amqp_url = "amqp://localhost:5672"

    @staticmethod
    def __workflow_service_client_factory(config_path, moniker, **kwargs):
        if kwargs is None or len(kwargs.keys()) == 0:
            return WorkflowStateService(moniker, CxOneFlowConfig.__default_amqp_url, None, None, True, PullRequestWorkflow())
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

            amqp_dict = CxOneFlowConfig.__get_value_for_key_or_default("amqp", kwargs, None)

            if not amqp_dict is None:
                amqp_url = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, "amqp-url", amqp_dict)
                amqp_user = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(amqp_dict, "amqp-user", None)
                amqp_password = CxOneFlowConfig.__get_secret_from_value_of_key_or_default(amqp_dict, "amqp-password", None)
                ssl_verify = CxOneFlowConfig.__get_value_for_key_or_default("ssl-verify", amqp_dict, True)
                
                return WorkflowStateService(moniker, amqp_url, amqp_user, amqp_password, ssl_verify, pr_workflow, \
                                            int(CxOneFlowConfig.__get_value_for_key_or_default("poll-max-interval-seconds", scan_monitor_dict, 600)),\
                                            int(CxOneFlowConfig.__get_value_for_key_or_default("poll-backoff-multiplier", scan_monitor_dict, 2)))
            else:
                return WorkflowStateService(moniker, CxOneFlowConfig.__default_amqp_url, None, None, True, pr_workflow)

            

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
                CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', kwargs, True) \
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
                CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', kwargs, True) \
                )

        return None


    __ordered_scm_config_tuples = {}
    __scm_config_tuples_by_service_moniker = {}

    __minimum_api_auth_keys = ['token', 'password']
    __basic_auth_keys = ['username', 'password']
    __all_possible_api_auth_keys = list(set(__minimum_api_auth_keys + __basic_auth_keys))

    __minimum_clone_auth_keys = __minimum_api_auth_keys + ['ssh']
    __all_possible_clone_auth_keys = list(set(__minimum_clone_auth_keys + __basic_auth_keys + ['ssh-port']))

    @staticmethod
    def __scm_api_auth_factory(api_auth_factory, config_dict, config_path):

        CxOneFlowConfig.__validate_no_extra_auth_keys(config_dict, CxOneFlowConfig.__all_possible_api_auth_keys, config_path)
        
        if len(CxOneFlowConfig.__validate_minimum_auth_keys(config_dict, CxOneFlowConfig.__minimum_api_auth_keys, config_path)) > 0:
            return api_auth_factory(CxOneFlowConfig.__get_secret_from_value_of_key_or_default(config_dict, "username", None),
                                    CxOneFlowConfig.__get_secret_from_value_of_key_or_default(config_dict, "password", None),
                                    CxOneFlowConfig.__get_secret_from_value_of_key_or_default(config_dict, "token", None))

        raise ConfigurationException(f"{config_path} SCM API authorization configuration is invalid!")

    @staticmethod
    def __validate_minimum_auth_keys(config_dict, valid_keys, config_path):
        auth_type_keys = [x for x in config_dict.keys() if x in valid_keys]
        if len(auth_type_keys) > 1:
            raise ConfigurationException.mutually_exclusive(config_path, auth_type_keys)
        return auth_type_keys


    @staticmethod
    def __validate_no_extra_auth_keys(config_dict, valid_keys, config_path):
        extra_passed_keys = config_dict.keys() - valid_keys

        if len(extra_passed_keys) > 0:
            raise ConfigurationException.invalid_keys(config_path, extra_passed_keys)


    @staticmethod
    def __cloner_factory(scm_cloner_factory, clone_auth_dict, config_path):

        CxOneFlowConfig.__validate_no_extra_auth_keys(clone_auth_dict, CxOneFlowConfig.__all_possible_clone_auth_keys, config_path)

        ssh_secret = CxOneFlowConfig.__get_value_for_key_or_default('ssh', clone_auth_dict, None)
        if ssh_secret is not None:
            ssh_secret = Path(CxOneFlowConfig.__secret_root) / Path(ssh_secret)

        retval = scm_cloner_factory(CxOneFlowConfig.__get_secret_from_value_of_key_or_default(clone_auth_dict, 'username', None),
                                  CxOneFlowConfig.__get_secret_from_value_of_key_or_default(clone_auth_dict, 'password', None),
                                  CxOneFlowConfig.__get_secret_from_value_of_key_or_default(clone_auth_dict, 'token', None),
                                  ssh_secret,
                                  CxOneFlowConfig.__get_value_for_key_or_default('ssh-port', clone_auth_dict, None))

        if retval is None:
            raise ConfigurationException(f"{config_path} SCM clone authorization configuration is invalid!")
        
        return retval

    @staticmethod
    def __setup_scm(cloner_factory, api_auth_factory, scm_class, config_dict, config_path):
        repo_matcher = re.compile(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'repo-match', config_dict), re.IGNORECASE)

        service_moniker = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'service-name', config_dict)

        cxone_client = CxOneFlowConfig.__cxone_client_factory(f"{config_path}/cxone", 
                                                            **(CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'cxone', config_dict)))
        
        workflow_service_client = CxOneFlowConfig.__workflow_service_client_factory(f"{config_path}/feedback", service_moniker, 
                                                                **(CxOneFlowConfig.__get_value_for_key_or_default('feedback', config_dict, {})))

        scan_config_dict = CxOneFlowConfig.__get_value_for_key_or_default('scan-config', config_dict, {} )

        cxone_service = CxOneService(service_moniker, cxone_client, \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-scan-engines', scan_config_dict, None), \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-scan-tags', scan_config_dict, None), \
                                     CxOneFlowConfig.__get_value_for_key_or_default('default-project-tags', scan_config_dict, None), \
                                     )

        connection_config_dict = CxOneFlowConfig.__get_value_for_key_or_fail(config_path, 'connection', config_dict)


        api_auth_dict = CxOneFlowConfig.__get_value_for_key_or_fail(f"{config_path}/connection", 'api-auth', connection_config_dict)

        api_session = APISession(CxOneFlowConfig.__get_value_for_key_or_fail(f"{config_path}/connection", 'base-url', connection_config_dict), \
                                 CxOneFlowConfig.__scm_api_auth_factory(api_auth_factory, api_auth_dict, f"{config_path}/connection/api-auth"), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('timeout-seconds', connection_config_dict, 60), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('retries', connection_config_dict, 3), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('proxies', connection_config_dict, None), \
                                 CxOneFlowConfig.__get_value_for_key_or_default('ssl-verify', connection_config_dict, True), \
                                )
        
        scm_shared_secret = CxOneFlowConfig.__get_secret_from_value_of_key_or_fail(f"{config_path}/connection", 'shared-secret', connection_config_dict)
        secret_test_result = CxOneFlowConfig.__shared_secret_policy.test(scm_shared_secret)
        if not len(secret_test_result) == 0:
            raise ConfigurationException(f"{config_path}/connection/shared-secret fails some complexity requirements: {secret_test_result}")
        
        clone_auth_dict = CxOneFlowConfig.__get_value_for_key_or_default('clone-auth', connection_config_dict, None)
        clone_config_path = f"{config_path}/connection/clone-auth"
        if clone_auth_dict is None:
            clone_auth_dict = api_auth_dict
            clone_config_path = f"{config_path}/connection/api-auth"
               
        scm_service = scm_class(service_moniker, api_session, scm_shared_secret, CxOneFlowConfig.__cloner_factory(cloner_factory, clone_auth_dict, clone_config_path))

        return repo_matcher, cxone_service, scm_service, workflow_service_client


    __cloner_factories = {
        'bbdc' : bitbucketdc_cloner_factory,
        'adoe' : adoe_cloner_factory }

    __auth_factories = {
        'bbdc' : bbdc_api_auth_factory,
        'adoe' : adoe_api_auth_factory }
        
    __scm_factories = {
        'bbdc' : BBDCService,
        'adoe' : ADOEService }

        


