import logging, asyncio, aio_pika, os
import cxoneflow_logging as cof_logging
from agent import mq_agent


__log = logging.getLogger("ResolverAgent")

async def spawn_agents():
    pass
    # async with asyncio.TaskGroup() as g:
    #     for moniker in CxOneFlowConfig.get_service_monikers():
    #         services = CxOneFlowConfig.retrieve_services_by_moniker(moniker)


if __name__ == '__main__':
    # try:
        # CxOneFlowConfig.bootstrap(get_config_path())
        asyncio.run(spawn_agents())
    # except ConfigurationException as ce:
        # __log.exception(ce)
