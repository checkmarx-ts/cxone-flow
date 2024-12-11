import logging, asyncio, aio_pika
import cxoneflow_logging as cof_logging
from config import ConfigurationException, get_config_path
from config.server import CxOneFlowConfig
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging import (
    ScanAwaitMessage,
    ScanAnnotationMessage,
    ScanFeedbackMessage,
)
from agent.resolver import ResolverResultsAgent
from agent import mq_agent

cof_logging.bootstrap()

__log = logging.getLogger("WorkflowAgent")


async def process_poll(msg: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        __log.debug(
            f"Received scan polling message on channel {msg.channel.number}: {msg.info()}"
        )
        sm = ScanAwaitMessage.from_binary(msg.body)
        services = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
        await services.pr.execute_poll_scan_workflow(msg, services.cxone)
    except BaseException as ex:
        __log.exception(ex)


async def process_pr_annotate(msg: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        __log.debug(
            f"Received PR annotation message on channel {msg.channel.number}: {msg.info()}"
        )
        sm = ScanAnnotationMessage.from_binary(msg.body)
        services = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
        await services.pr.execute_pr_annotate_workflow(
            msg, services.cxone, services.scm
        )
    except BaseException as ex:
        __log.exception(ex)


async def process_pr_feedback(msg: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        __log.debug(
            f"Received PR feedback message on channel {msg.channel.number}: {msg.info()}"
        )
        sm = ScanFeedbackMessage.from_binary(msg.body)
        services = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)
        await services.pr.execute_pr_feedback_workflow(
            msg, services.cxone, services.scm
        )
    except BaseException as ex:
        __log.exception(ex)


async def spawn_agents():

    async with asyncio.TaskGroup() as g:
        for moniker in CxOneFlowConfig.get_service_monikers():
            services = CxOneFlowConfig.retrieve_services_by_moniker(moniker)
            g.create_task(
                mq_agent(
                    process_poll,
                    await services.pr.mq_client(),
                    moniker,
                    PRFeedbackService.QUEUE_SCAN_POLLING,
                )
            )
            g.create_task(
                mq_agent(
                    process_pr_annotate,
                    await services.pr.mq_client(),
                    moniker,
                    PRFeedbackService.QUEUE_ANNOTATE_PR,
                )
            )
            g.create_task(
                mq_agent(
                    process_pr_feedback,
                    await services.pr.mq_client(),
                    moniker,
                    PRFeedbackService.QUEUE_FEEDBACK_PR,
                )
            )
            g.create_task(
                mq_agent(
                    ResolverResultsAgent(services),
                    await services.resolver.mq_client(),
                    moniker,
                    ResolverScanService.QUEUE_RESOLVER_COMPLETE,
                )
            )


if __name__ == "__main__":
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
        asyncio.run(spawn_agents())
    except ConfigurationException as ce:
        __log.exception(ce)
