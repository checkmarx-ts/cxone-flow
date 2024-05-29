import asyncio, aio_pika, logging
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path

cof_logging.bootstrap()

__log = logging.getLogger("RabbitSetup")


async def setup() -> None:
    monikers = CxOneFlowConfig.get_service_monikers()
    
    rmq = await aio_pika.connect_robust("amqp://localhost")

    async with rmq.channel() as channel:
        scan_in_exchange = await channel.declare_exchange("Scan In", aio_pika.ExchangeType.FANOUT, durable=True)
        scan_await_exchange = await channel.declare_exchange("Scan Await", aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
        scan_feedback_exchange = await channel.declare_exchange("Scan Feedback", aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
        polling_delivery_exchange = await channel.declare_exchange("Scan Polling Delivery", aio_pika.ExchangeType.DIRECT, durable=True, internal=True)

        polling_scans_queue = await channel.declare_queue("Polling Scans", durable=True)
        awaited_scans_queue = await channel.declare_queue("Awaited Scans", durable=True, \
                                arguments = {
                                    'x-dead-letter-exchange' : 'Scan Polling Delivery',
                                    'x-dead-letter-routing-key' : 'poll'})

        pr_feedback_queue = await channel.declare_queue("PR Feedback", durable=True)
        
        await polling_scans_queue.bind(polling_delivery_exchange, "poll")
        await awaited_scans_queue.bind(scan_await_exchange, "await.*.*")
        await pr_feedback_queue.bind(scan_feedback_exchange, "feedback.pr.*")
        await scan_await_exchange.bind(scan_in_exchange)
        await scan_feedback_exchange.bind(scan_in_exchange)


if __name__ == "__main__":
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
        asyncio.run(setup())
    except ConfigurationException as ce:
        __log.exception(ce)
