from .. import ConfigurationException, RouteNotFoundException, CommonConfig
from agent.resolver import ResolverOpts, ResolverRunnerAgent
from agent.resolver.resolver_runner import ResolverRunner
from agent.resolver.shell_runner import ShellRunner
from agent.resolver.toolkit_runner import ToolkitRunner
from typing import List


class ResolverConfig(CommonConfig):

    __agents = []


    @staticmethod
    def agent_handlers() -> List[ResolverRunnerAgent]:
        return ResolverConfig.__agents

    @staticmethod
    def __resolver_opts_factory(config_dict : dict) -> ResolverOpts:
      return ResolverOpts(config_dict)
    
    @staticmethod
    def __resolver_runner_factory(config_path : str, config_dict : dict) -> ResolverRunner:
        opts = ResolverConfig.__resolver_opts_factory(CommonConfig._get_value_for_key_or_default("resolver-opts", config_dict, None))
        work_path = CommonConfig._get_value_for_key_or_default("resolver-work-path", config_dict, "/tmp/resolver")
        container_runner_cfg = CommonConfig._get_value_for_key_or_default("run-with-container", config_dict, None)

        if container_runner_cfg is None:
            return ShellRunner(work_path, opts, 
                               CommonConfig._get_value_for_key_or_fail(config_path, "resolver-path", config_dict), 
                               CommonConfig._get_value_for_key_or_default("resolver-run-as", config_dict, None))
        else:
            return ToolkitRunner(work_path, opts,
                                 CommonConfig._get_value_for_key_or_fail(f"{config_path}/run-with-container", "supply-chain-toolkit-path", container_runner_cfg),
                                 CommonConfig._get_value_for_key_or_fail(f"{config_path}/run-with-container", "container-image-tag", container_runner_cfg),
                                 CommonConfig._get_value_for_key_or_default("use-running-uid", container_runner_cfg, True),
                                 CommonConfig._get_value_for_key_or_default("use-running-gid", container_runner_cfg, True),
                                 )

    @staticmethod
    def __agent_factory(config_path : str, agent_tag : str, config_dict : dict) -> ResolverRunnerAgent:
        return ResolverRunnerAgent(
            agent_tag,
            bytes(CommonConfig._get_secret_from_value_of_key_or_fail(config_path, "public-key", config_dict), 'UTF-8'),
            ResolverConfig.__resolver_runner_factory(config_path, config_dict), 
            CommonConfig._load_amqp_settings(config_path, **config_dict))

    @staticmethod
    def bootstrap(config_file_path = "./resolver_config.yaml"):
        try:
            ResolverConfig.log().info(f"Loading configuration from {config_file_path}")

            raw_yaml = CommonConfig.load_yaml(config_file_path)
            CommonConfig._secret_root = ResolverConfig._get_value_for_key_or_fail("", "secret-root-path", raw_yaml)

            serviced_tags = ResolverConfig._get_value_for_key_or_fail("", "serviced-tags", raw_yaml)

            if serviced_tags is not None:
                for tag in serviced_tags:
                    ResolverConfig.__agents.append(ResolverConfig.__agent_factory(f"serviced-tags/{tag}", tag, serviced_tags[tag]))
        except Exception as ex:
            ResolverConfig.log().exception(ex)
            raise
        

