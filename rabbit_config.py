import asyncio, aio_pika, logging
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from workflows.state_service import WorkflowStateService


cof_logging.bootstrap()

__log = logging.getLogger("RabbitSetup")


async def setup() -> None:
    monikers = CxOneFlowConfig.get_service_monikers()

    for moniker in monikers:
        __log.info(f"Configuring RabbitMQ for {moniker}")
        _,_,workflow_service = CxOneFlowConfig.retrieve_services_by_moniker(moniker)

        rmq = await workflow_service.mq_client()

        async with rmq.channel() as channel:
            scan_in_exchange = await channel.declare_exchange(WorkflowStateService.EXCHANGE_SCAN_INPUT, aio_pika.ExchangeType.FANOUT, durable=True)
            scan_await_exchange = await channel.declare_exchange(WorkflowStateService.EXCHANGE_SCAN_WAIT, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            scan_feedback_exchange = await channel.declare_exchange(WorkflowStateService.EXCHANGE_SCAN_FEEDBACK, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            polling_delivery_exchange = await channel.declare_exchange(WorkflowStateService.EXCHANGE_SCAN_POLLING, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)

            polling_scans_queue = await channel.declare_queue(WorkflowStateService.get_poll_queue_name(moniker), durable=True)
            awaited_scans_queue = await channel.declare_queue(WorkflowStateService.QUEUE_SCAN_WAIT, durable=True, \
                                    arguments = {
                                        'x-dead-letter-exchange' : WorkflowStateService.EXCHANGE_SCAN_POLLING})

            pr_feedback_queue = await channel.declare_queue(WorkflowStateService.QUEUE_FEEDBACK_PR, durable=True)
            
            await polling_scans_queue.bind(polling_delivery_exchange, WorkflowStateService.get_poll_binding_topic(moniker))
            await awaited_scans_queue.bind(scan_await_exchange, WorkflowStateService.ROUTEKEY_SCAN_WAIT)
            await pr_feedback_queue.bind(scan_feedback_exchange, WorkflowStateService.ROUTEKEY_FEEDBACK_PR)
            await scan_await_exchange.bind(scan_in_exchange)
            await scan_feedback_exchange.bind(scan_in_exchange)


if __name__ == "__main__":
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
        asyncio.run(setup())
    except ConfigurationException as ce:
        __log.exception(ce)
