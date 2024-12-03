from _version import __version__
from _agent import __agent__
from typing import Tuple, List
import os
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

