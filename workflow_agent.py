import logging, asyncio, aio_pika, os
import cxoneflow_logging as cof_logging
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from workflows import WorkflowStateService
from workflows.messaging import ScanAwaitMessage
from cxone_api.scanning import ScanLoader, ScanInspector

cof_logging.bootstrap()

__log = logging.getLogger("WorkflowAgent")


async def process_poll(msg : aio_pika.abc.AbstractIncomingMessage) -> None:
    __log.debug(f"Reveived scan polling message on channel {msg.channel.number}: {msg.info()}")

    sm = ScanAwaitMessage.from_binary(msg.body)

    # TODO: Make another method that just acks if config is set to not handle feedback.  This will
    # avoid needing to talk to CxOne.
    if sm.is_expired():
        __log.warn(f"Scan id {sm.scanid} polling timeout expired at {sm.drop_by}. Polling for this scan has been stopped.")
        await msg.ack()
    else:
        cxone, _, wf = CxOneFlowConfig.retrieve_services_by_moniker(sm.moniker)

        inspector = await ScanLoader.load(cxone, sm.scanid)

        if not inspector.executing:
            if inspector.successful:
                pass
                # This should be in the workflow class...
                # Scan success, publish new message with same workflow state topic set for feedback
                # ack this message
            else:
                # This should be in the workflow class...
                # Log scan failure
                # Publish new message for annotation (new state)
                # ack this message
                pass
        else:
            # This should be in the workflow class...
            # Form a new message with the same routing key
            # Set expiration by min(original-expiration * backoff, max backoff)
            # Publish the new message
            # Ack the old message
            pass
        
        pass

    await msg.nack()
    pass


async def agent():
    _, _, wfs = CxOneFlowConfig.retrieve_services_by_moniker("ADO-cloud")

    qname = WorkflowStateService.get_poll_queue_name("ADO-cloud")

    async with (await wfs.mq_client()).channel() as channel:
        await channel.set_qos(prefetch_count=2)
        q = await channel.get_queue(qname)

        await q.consume(process_poll, arguments = {
            "moniker" : "ADO-cloud"}, consumer_tag = f"ADO-cloud.{os.getpid()}")

        while True:
            await asyncio.Future()

if __name__ == '__main__':
    try:
        CxOneFlowConfig.bootstrap(get_config_path())
    except ConfigurationException as ce:
        __log.exception(ce)

    asyncio.run(agent())


