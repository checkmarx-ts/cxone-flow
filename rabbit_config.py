import asyncio, aio_pika, logging
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService


cof_logging.bootstrap()

__log = logging.getLogger("RabbitSetup")


async def setup() -> None:
    monikers = CxOneFlowConfig.get_service_monikers()

    for moniker in monikers:
        __log.info(f"Configuring RabbitMQ for {moniker}")
        services = CxOneFlowConfig.retrieve_services_by_moniker(moniker)

        pr_rmq = await services.pr.mq_client()

        async with pr_rmq.channel() as channel:
            # All scans come in to the Scan In exchange.  It fans out to:
            # * Scan Annotation
            # * Scan Feedback
            # * Scan Await
            # * SCA Resolver Scan
            # Bindings in each of these exchanges route the message to the correct queue
            scan_in_exchange = await channel.declare_exchange(PRFeedbackService.EXCHANGE_SCAN_INPUT, aio_pika.ExchangeType.FANOUT, durable=True)
            scan_await_exchange = await channel.declare_exchange(PRFeedbackService.EXCHANGE_SCAN_WAIT, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            scan_annotate_exchange = await channel.declare_exchange(PRFeedbackService.EXCHANGE_SCAN_ANNOTATE, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            scan_feedback_exchange = await channel.declare_exchange(PRFeedbackService.EXCHANGE_SCAN_FEEDBACK, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)

            # Bind "Scan In" Exchange to all the routing exchanges
            await scan_await_exchange.bind(scan_in_exchange)
            await scan_feedback_exchange.bind(scan_in_exchange)
            await scan_annotate_exchange.bind(scan_in_exchange)

            
            # The awaited scans allows scans to soak until a timeout, then they go to the polling exchange where the
            # scan is polled to see the state or times out.
            polling_delivery_exchange = await channel.declare_exchange(PRFeedbackService.EXCHANGE_SCAN_POLLING, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            awaited_scans_queue = await channel.declare_queue(PRFeedbackService.QUEUE_SCAN_WAIT, durable=True, \
                                    arguments = {
                                        'x-queue-type' : "quorum",
                                        'x-dead-letter-strategy' : "at-least-once",
                                        'x-overflow' : "reject-publish",
                                        'x-dead-letter-exchange' : PRFeedbackService.EXCHANGE_SCAN_POLLING
                                        })
            await awaited_scans_queue.bind(scan_await_exchange, PRFeedbackService.ROUTEKEY_POLL_BINDING)
            polling_scans_queue = await channel.declare_queue(PRFeedbackService.QUEUE_SCAN_POLLING, durable=True, arguments={'x-queue-type' : "quorum"})
            await polling_scans_queue.bind(polling_delivery_exchange, PRFeedbackService.ROUTEKEY_POLL_BINDING)

            # Once polling is complete, a feedback message for the correct workflow is created.

            # Scan state: Feedback
            # Available workflows:
            # * PR - Pull Request feedback writted to the PR comments
            pr_feedback_queue = await channel.declare_queue(PRFeedbackService.QUEUE_FEEDBACK_PR, durable=True, arguments={'x-queue-type' : "quorum"})
            await pr_feedback_queue.bind(scan_feedback_exchange, PRFeedbackService.ROUTEKEY_FEEDBACK_PR)

            # Scan State: Annotation
            # Available workflows:
            # * PR - Pull request annotation to indicate scan progress. 
            pr_annotate_queue = await channel.declare_queue(PRFeedbackService.QUEUE_ANNOTATE_PR, durable=True, arguments={'x-queue-type' : "quorum"})
            await pr_annotate_queue.bind(scan_annotate_exchange, PRFeedbackService.ROUTEKEY_ANNOTATE_PR)


        resolver_rmq = await services.resolver.mq_client()
        async with resolver_rmq.channel() as channel:
            # Resolver scan queue configuration
            sca_resolver_scan_exchange = await channel.declare_exchange(ResolverScanService.EXCHANGE_RESOLVER_SCAN, aio_pika.ExchangeType.TOPIC, durable=True, internal=True)
            resolver_scans_exec_queue = await channel.declare_queue(ResolverScanService.QUEUE_RESOLVER_EXEC, durable=True, arguments={'x-queue-type' : "quorum"})
            await resolver_scans_exec_queue.bind(sca_resolver_scan_exchange, ResolverScanService.ROUTEKEY_EXEC_SCA_SCAN)

            resolver_scans_complete_queue = await channel.declare_queue(ResolverScanService.QUEUE_RESOLVER_COMPLETE, durable=True, 
                                                                        arguments={'x-queue-type' : "quorum"})
            await resolver_scans_complete_queue.bind(sca_resolver_scan_exchange, ResolverScanService.ROUTEKEY_EXEC_SCA_SCAN_COMPLETE)



if __name__ == "__main__":
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
        asyncio.run(setup())
    except ConfigurationException as ce:
        __log.exception(ce)
