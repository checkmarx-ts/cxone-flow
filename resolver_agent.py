import logging, asyncio
import cxoneflow_logging as cof_logging
from agent import mq_agent
from config.resolver import ResolverConfig
from config import ConfigurationException, get_config_path
from workflows.resolver_scan_service import ResolverScanService

cof_logging.bootstrap()

__log = logging.getLogger("ResolverAgent")

async def spawn_agents():
    async with asyncio.TaskGroup() as g:
        for agent in ResolverConfig.agent_handlers():
            g.create_task(mq_agent(agent, await agent.mq_client(), agent.tag, 
                                   ResolverScanService.make_queuename_for_tag(agent.tag), 1))


if __name__ == '__main__':
    try:
        ResolverConfig.bootstrap(get_config_path())
        asyncio.run(spawn_agents())
    except ConfigurationException as ce:
        __log.exception(ce)
