from .. import ConfigurationException, RouteNotFoundException, CommonConfig
from agent.resolver import ResolverOpts, ResolverRunnerAgent
from agent.resolver.resolver_runner import ResolverRunner
from agent.resolver.shell_runner import ResolverShellRunner
from agent.resolver.toolkit_runner import ResolverToolkitRunner
from agent.resolver.noresolver_runner import NoResolverRunner
from agent.resolver.two_stage_runner import ResolverTwoStageRunner
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
        work_path = CommonConfig._get_value_for_key_or_default_warn_deprecated("scan-agent-work-path", "resolver-work-path", 
                                                                               config_path, config_dict, "/tmp")
        container_runner_cfg = CommonConfig._get_value_for_key_or_default_warn_deprecated("run-resolver-with-container", "run-with-container", 
                                                                                          config_path, config_dict, None)
        disable_resolver = CommonConfig._get_value_for_key_or_default("disable-resolver", config_dict, False)
        resolver_path = CommonConfig._get_value_for_key_or_default("resolver-path", config_dict, None)

        resolver_runner = None

        if disable_resolver:
            resolver_runner = NoResolverRunner()
        elif resolver_path is not None:
            resolver_runner = ResolverShellRunner(work_path, opts, 
                               resolver_path, 
                               CommonConfig._get_value_for_key_or_default("resolver-run-as", config_dict, None))
        elif container_runner_cfg is not None:
            resolver_runner = ResolverToolkitRunner(work_path, opts,
                                 CommonConfig._get_value_for_key_or_fail(f"{config_path}/run-resolver-with-container", 
                                                                         "supply-chain-toolkit-path", container_runner_cfg),
                                 CommonConfig._get_value_for_key_or_fail(f"{config_path}/run-resolver-with-container", 
                                                                         "container-image-tag", container_runner_cfg),
                                 CommonConfig._get_value_for_key_or_default("use-running-uid", container_runner_cfg, True),
                                 CommonConfig._get_value_for_key_or_default("use-running-gid", container_runner_cfg, True),
                                 )
        else:
            raise ConfigurationException.missing_at_least_one_key_path(config_path, ["disable-resolver", "run-resolver-with-container", "resolver-path"])

    
        prescan_dict = CommonConfig._get_value_for_key_or_default("pre-scan", config_dict, None)

        if prescan_dict is None:
            return resolver_runner
        else:
            return ResolverTwoStageRunner(work_path, opts, resolver_runner, 
                        CommonConfig._get_value_for_key_or_default("resolver-before-script", prescan_dict, False),
                        CommonConfig._get_value_for_key_or_fail(f"{config_path}/pre-scan", "container-image-tag", prescan_dict),
                        CommonConfig._get_value_for_key_or_default("shell", prescan_dict, "/bin/sh"),
                        CommonConfig._get_value_for_key_or_fail(f"{config_path}/pre-scan", "script", prescan_dict),
                        CommonConfig._get_value_for_key_or_default("run-as-agent", prescan_dict, True))

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
        

