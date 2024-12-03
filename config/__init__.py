from _version import __version__
from _agent import __agent__
from typing import Tuple, List, Union
import os, logging, cxone_api as cx
from multiprocessing import cpu_count
from pathlib import Path
from cxoneflow_logging import SecretRegistry

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

    return loglevel


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


class CommonConfig:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

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

        CommonConfig.log().warning("************SSL verification is turned OFF************")
        CommonConfig.log().warning("A path to the default CA bundle could not be determined.  Please set the REQUESTS_CA_BUNDLE environment variable.")
        return False

    @staticmethod
    def _get_value_for_key_or_fail(config_path, key, config_dict):
        if not key in config_dict.keys():
            raise ConfigurationException.missing_key_path(f"{config_path}/{key}")
        else:
            return config_dict[key]

    @staticmethod
    def _get_file_contents_from_value_of_key_or_default(config_dict, key, default):
        if not key in config_dict.keys():
            return default
        else:
            if not os.path.isfile(Path(CommonConfig._secret_root) / Path(config_dict[key])):
                return default
            else:
                with open(Path(CommonConfig._secret_root) / Path(config_dict[key]), "rt") as f:
                    return f.read().strip()


    @staticmethod
    def _get_secret_from_value_of_key_or_default(config_dict, key, default):
        return SecretRegistry.register(CommonConfig._get_file_contents_from_value_of_key_or_default(config_dict, key, default))

    @staticmethod
    def _get_secret_from_value_of_key_or_fail(config_path, key, config_dict):
        retval = CommonConfig._get_secret_from_value_of_key_or_default(config_dict, key, None)

        if retval is None:
            raise ConfigurationException.secret_load_error(f"{config_path}/{key}")
        
        return retval


    @staticmethod
    def _get_value_for_key_or_default(key, config_dict, default):
        if config_dict is None or not key in config_dict.keys():
            return default
        else:
            return config_dict[key]


    _default_amqp_url = "amqp://localhost:5672"


    @staticmethod
    def _load_amqp_settings(config_path, **kwargs) -> Union[str, str, str, bool]:
        amqp_dict = CommonConfig._get_value_for_key_or_default("amqp", kwargs, None)
        if not amqp_dict is None:
            amqp_url = CommonConfig._get_value_for_key_or_fail(config_path, "amqp-url", amqp_dict)
            amqp_user = CommonConfig._get_secret_from_value_of_key_or_default(amqp_dict, "amqp-user", None)
            amqp_password = CommonConfig._get_secret_from_value_of_key_or_default(amqp_dict, "amqp-password", None)
            ssl_verify = CommonConfig._get_value_for_key_or_default("ssl-verify", amqp_dict, CommonConfig.get_default_ssl_verify_value())
            return amqp_url, amqp_user, amqp_password, ssl_verify
        else:
            return CommonConfig._default_amqp_url, None, None, True
        

    @staticmethod
    def _cxone_client_factory(config_path, **kwargs):

        always_required = ['tenant', 'iam-endpoint', 'api-endpoint']

        if len(always_required - kwargs.keys()) != 0:
            raise ConfigurationException.missing_keys(config_path, always_required)

        one_required = ['api-key','oauth']
        one_found = len([x for x in one_required if x in kwargs.keys()])

        if one_found != 1:
            raise ConfigurationException.mutually_exclusive(config_path, one_required)
        

        tenant_name = CommonConfig._get_value_for_key_or_fail(config_path, 'tenant', kwargs)

        iam_endpoint_value = CommonConfig._get_value_for_key_or_fail(config_path, 'iam-endpoint', kwargs)
        tenant_auth_endpoint = None
        if iam_endpoint_value in cx.AuthRegionEndpoints.keys():
            tenant_auth_endpoint = cx.AuthRegionEndpoints[iam_endpoint_value](tenant_name)
        else:
            tenant_auth_endpoint = cx.CxOneAuthEndpoint(tenant_name, iam_endpoint_value)


        api_endpoint_value = CommonConfig._get_value_for_key_or_fail(config_path, 'api-endpoint', kwargs)
        tenant_api_endpoint = None
        if api_endpoint_value in cx.ApiRegionEndpoints.keys():
            tenant_api_endpoint = cx.ApiRegionEndpoints[api_endpoint_value]()
        else:
            tenant_api_endpoint = cx.CxOneApiEndpoint(api_endpoint_value)

        if 'api-key' in kwargs.keys():
            return cx.CxOneClient.create_with_api_key(
                CommonConfig._get_secret_from_value_of_key_or_fail(config_path, 'api-key', kwargs), \
                __agent__, \
                tenant_auth_endpoint, \
                tenant_api_endpoint, \
                CommonConfig._get_value_for_key_or_default('timeout-seconds', kwargs, 60), \
                CommonConfig._get_value_for_key_or_default('retries', kwargs, 3), \
                CommonConfig._get_value_for_key_or_default('proxies', kwargs, None), \
                CommonConfig._get_value_for_key_or_default('ssl-verify', kwargs, CommonConfig.get_default_ssl_verify_value()) \
                )
        elif 'oauth' in kwargs.keys():
            oauth_params = CommonConfig._get_value_for_key_or_fail(config_path, 'oauth', kwargs)
            oauth_id = CommonConfig._get_secret_from_value_of_key_or_fail(f"{config_path}/oauth", 'client-id', oauth_params)
            oauth_secret = CommonConfig._get_secret_from_value_of_key_or_fail(f"{config_path}/oauth", 'client-secret', oauth_params)

            return cx.CxOneClient.create_with_oauth(
                oauth_id, oauth_secret, \
                __agent__, \
                tenant_auth_endpoint, \
                tenant_api_endpoint, \
                CommonConfig._get_value_for_key_or_default('timeout-seconds', kwargs, 60), \
                CommonConfig._get_value_for_key_or_default('retries', kwargs, 3), \
                CommonConfig._get_value_for_key_or_default('proxies', kwargs, None), \
                CommonConfig._get_value_for_key_or_default('ssl-verify', kwargs, CommonConfig.get_default_ssl_verify_value()) \
                )

        return None
