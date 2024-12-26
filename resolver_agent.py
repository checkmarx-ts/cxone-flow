import logging, asyncio
import cxoneflow_logging as cof_logging
from agent import mq_agent
from config.resolver import ResolverConfig
from config import ConfigurationException, get_config_path
from workflows.resolver_scan_service import ResolverScanService
from subprocess import CalledProcessError
from _version import __version__

cof_logging.bootstrap()

__log = logging.getLogger("ResolverRunnerAgent")


async def spawn_agents():
    __log.info(f"Resolver Agent {__version__} Startup")
    async with asyncio.TaskGroup() as g:
        for agent in ResolverConfig.agent_handlers():
            g.create_task(
                mq_agent(
                    agent,
                    await agent.mq_client(),
                    agent.tag,
                    ResolverScanService.make_queuename_for_tag(agent.tag),
                    1,
                )
            )


if __name__ == "__main__":
    try:
        ResolverConfig.bootstrap(get_config_path())
        asyncio.run(spawn_agents())
    except CalledProcessError as cpex:
        __log.exception(f"stdout: [{cpex.stdout}] stderr: [{cpex.stderr}]", cpex)
    except ConfigurationException as ce:
        __log.exception(ce)
