from .. import ConfigurationException, RouteNotFoundException, CommonConfig
from agent.resolver import ResolverOpts, ResolverAgent
from typing import List

class ResolverConfig(CommonConfig):

    __agents = []


    @staticmethod
    def agent_handlers() -> List[ResolverAgent]:
        return ResolverConfig.__agents

    @staticmethod
    def __resolver_opts_factory(config_dict : dict) -> ResolverOpts:
      return ResolverOpts(
          persistent_log_path=CommonConfig._get_value_for_key_or_default("persistent-log-path", config_dict, None),
          fail_on_manifest_failure=CommonConfig._get_value_for_key_or_default("fail-on-manifest-failure", config_dict, True),
          verbose_logging=CommonConfig._get_value_for_key_or_default("verbose-logging", config_dict, False),
          scan_containers=CommonConfig._get_value_for_key_or_default("scan-containers", config_dict, False),
          ssl_verify=CommonConfig._get_value_for_key_or_default("ssl-verify", config_dict, True),
          proxy=CommonConfig._get_value_for_key_or_default("proxy", config_dict, None))

    @staticmethod
    def __agent_factory(config_path : str, agent_tag : str, config_dict : dict) -> ResolverAgent:
        return ResolverAgent(
            agent_tag,
            bytes(CommonConfig._get_secret_from_value_of_key_or_fail(config_path, "public-key", config_dict), 'UTF-8'),
            ResolverConfig.__resolver_opts_factory(CommonConfig._get_value_for_key_or_default("resolver-opts", config_dict, None)),
            CommonConfig._get_value_for_key_or_default("toolkit-location", config_dict, "/opt/cx-supply-chain-toolkit"),
            CommonConfig._get_value_for_key_or_default("resolver-work-path", config_dict, "/tmp/resolver"),
            CommonConfig._get_value_for_key_or_fail(config_path, "resolver-path", config_dict),
            CommonConfig._load_amqp_settings(config_path, **config_dict))

    @staticmethod
    def bootstrap(config_file_path = "./resolver_config.yaml"):
        try:
            ResolverConfig.log().info(f"Loading configuration from {config_file_path}")

            raw_yaml = CommonConfig.load_yaml(config_file_path)
            CommonConfig._secret_root = ResolverConfig._get_value_for_key_or_fail("", "secret-root-path", raw_yaml)

            serviced_tags = ResolverConfig._get_value_for_key_or_fail("", "serviced-tags", raw_yaml)

            for tag in serviced_tags:
                ResolverConfig.__agents.append(ResolverConfig.__agent_factory(f"serviced-tags/{tag}", tag, serviced_tags[tag]))
        except Exception as ex:
            ResolverConfig.log().exception(ex)
            raise
        

