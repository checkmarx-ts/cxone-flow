import aio_pika, logging, pamqp.commands, asyncio
from datetime import timedelta
from workflows.messaging import ScanAwaitMessage
from workflows.base_service import CxOneFlowAbstractWorkflowService
from workflows import ScanStates
from cxone_service import CxOneService
from cxone_api.exceptions import ResponseException
from typing import List

class ScanPollingService(CxOneFlowAbstractWorkflowService):
    QUEUE_SCAN_POLLING = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}Polling Scans"
    QUEUE_SCAN_WAIT = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}Awaited Scans"

    ROUTEKEY_POLL_BINDING = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}*.{ScanStates.AWAIT}.*.*"


    @staticmethod
    def log():
        return logging.getLogger("ScanPollingService")

    def __init__(self, services : List[CxOneFlowAbstractWorkflowService], max_interval_seconds : timedelta, backoff_scalar : int, 
                 amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__max_interval = timedelta(seconds=max_interval_seconds)
        self.__backoff = backoff_scalar
        self.__services = services

    async def execute_poll_scan_workflow(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_service : CxOneService):

        requeue_on_finally = True

        swm = await self._safe_deserialize_body(msg, ScanAwaitMessage)
    
        if swm.is_expired():
            ScanPollingService.log().warning(f"Scan id {swm.scanid} polling timeout expired at {swm.drop_by}. Polling for this scan has been stopped.")
            await msg.ack()
        else:
            write_channel = None
            try:
                write_channel = await (await self.mq_client()).channel()
                inspector = await cxone_service.load_scan_inspector(swm.scanid)

                if not inspector.executing:
                    try:
                        requeue_on_finally = False
                        
                        if inspector.successful:
                            ScanPollingService.log().info(f"Scan success for scan id {swm.scanid}, enqueuing feedback workflow.")
                            await asyncio.gather(*[svc.handle_completed_scan(swm) for svc in self.__services])
                        else:
                            ScanPollingService.log().info(f"Scan failure for scan id {swm.scanid}, enqueuing feedback error workflow.")
                            await asyncio.gather(*[svc.handle_awaited_scan_error(swm, inspector.state_msg) for svc in self.__services])
                    except BaseException as bex:
                        ScanPollingService.log().exception(bex)
                    finally:
                            await msg.ack()

            except ResponseException as ex:
                ScanPollingService.log().exception(ex)
                ScanPollingService.log().error(f"Polling for scan id {swm.scanid} stopped due to exception.")
                requeue_on_finally = False
                await msg.ack()
            finally:
                if requeue_on_finally:
                    exchange = None
                    if write_channel:
                        exchange = await write_channel.get_exchange(CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)

                    if exchange:
                        orig_exp = int(msg.headers['x-death'][0]['original-expiration'])
                        backoff=min(timedelta(milliseconds=orig_exp * self.__backoff), self.__max_interval)
                        new_msg = aio_pika.Message(swm.to_binary(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                    expiration=backoff)

                        result = await exchange.publish(new_msg, routing_key=msg.routing_key)

                        if type(result) == pamqp.commands.Basic.Ack:
                            ScanPollingService.log().debug(f"Scan id {swm.scanid} poll message re-enqueued with delay {backoff.total_seconds()}s.")
                            await msg.ack()
                        else:
                            ScanPollingService.log().debug(f"Scan id {swm.scanid} failed to re-enqueue new poll message.")
                            await msg.nack()
                
                if write_channel is not None:
                    await write_channel.close()
