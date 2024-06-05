import logging, asyncio, aio_pika, os
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from workflows.state_service import WorkflowStateService
from workflows.messaging import ScanAwaitMessage, ScanAnnotationMessage
from typing import Any, Callable, Awaitable

cof_logging.bootstrap()

__log = logging.getLogger("WorkflowAgent")

async def process_poll(msg : aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        __log.debug(f"Reveived scan polling message on channel {msg.channel.number}: {msg.info()}")
        sm = ScanAwaitMessage.from_binary(msg.body)
        cxone, _, wf = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
        await wf.execute_poll_scan_workflow(msg, cxone)
    except BaseException as ex:
        __log.exception(ex)


async def process_pr_annotate(msg : aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        __log.debug(f"Reveived annotation message on channel {msg.channel.number}: {msg.info()}")
        sm = ScanAnnotationMessage.from_binary(msg.body)
        cxone, scm, wf = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
        await wf.execute_pr_annotate_workflow(msg, cxone, scm)
    except BaseException as ex:
        __log.exception(ex)

async def agent(coro : Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[Any]], moniker : str, queue : str):
    _, _, wfs = CxOneFlowConfig.retrieve_services_by_moniker(moniker)

    async with (await wfs.mq_client()).channel() as channel:
        await channel.set_qos(prefetch_count=2)
        q = await channel.get_queue(queue)

        await q.consume(coro, arguments = {
            "moniker" : moniker}, consumer_tag = f"{coro.__name__}.{moniker}.{os.getpid()}")

        while True:
            await asyncio.Future()


async def spawn_agents():

    async with asyncio.TaskGroup() as g:
        for moniker in CxOneFlowConfig.get_service_monikers():
            g.create_task(agent(process_poll, moniker, WorkflowStateService.QUEUE_SCAN_POLLING))
            g.create_task(agent(process_pr_annotate, moniker, WorkflowStateService.QUEUE_SCAN_PR_ANNOTATE))
   

if __name__ == '__main__':
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
    except ConfigurationException as ce:
        __log.exception(ce)

    asyncio.run(spawn_agents())


