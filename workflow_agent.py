import logging, asyncio, aio_pika, os
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from workflows.state_service import WorkflowStateService
from workflows.messaging import ScanAwaitMessage

cof_logging.bootstrap()

__log = logging.getLogger("WorkflowAgent")

async def process_poll(msg : aio_pika.abc.AbstractIncomingMessage) -> None:
    __log.debug(f"Reveived scan polling message on channel {msg.channel.number}: {msg.info()}")
    sm = ScanAwaitMessage.from_binary(msg.body)
    cxone, _, wf = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
    await wf.execute_poll_scan_workflow(msg, cxone)

async def poll_agent(moniker : str):
    _, _, wfs = CxOneFlowConfig.retrieve_services_by_moniker(moniker)

    async with (await wfs.mq_client()).channel() as channel:
        await channel.set_qos(prefetch_count=2)
        q = await channel.get_queue(WorkflowStateService.QUEUE_SCAN_POLLING)

        await q.consume(process_poll, arguments = {
            "moniker" : moniker}, consumer_tag = f"{moniker}.{os.getpid()}")

        while True:
            await asyncio.Future()

async def spawn_agents():

    async with asyncio.TaskGroup() as g:
        for moniker in CxOneFlowConfig.get_service_monikers():
            g.create_task(poll_agent(moniker))
   

if __name__ == '__main__':
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
    except ConfigurationException as ce:
        __log.exception(ce)

    asyncio.run(spawn_agents())


