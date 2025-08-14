import aio_pika, json
from time import perf_counter_ns
from workflows.feedback_workflow_base import AbstractFeedbackWorkflow
from workflows import ScanStates, ScanWorkflow, FeedbackWorkflow
from workflows.base_service import AMQPClient, CxOneFlowAbstractWorkflowService
from workflows.messaging import PushDetails, ScanAwaitMessage, ScanFeedbackMessage
from workflows.messaging.base_message import StampedMessage
from cxone_api import CxOneClient
from cxone_service import CxOneException
from cxone_sarif.opts import ReportOpts
from cxone_sarif import get_sarif_v210_log_for_scan
from sarif_om import SarifLog
from api_utils import gen_signature_header
from dataclasses import dataclass, asdict, make_dataclass
from dataclasses_json import dataclass_json
from typing import List, Dict

class PushFeedbackService(CxOneFlowAbstractWorkflowService):
    PUSH_ELEMENT_PREFIX = "push:"
    PUSH_TOPIC_PREFIX = "push."

    EXCHANGE_SARIF_WORK = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Sarif Workflows"

    QUEUE_SARIF_GEN = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Generate Sarif"
    ROUTEKEY_GEN_SARIF = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH_GEN}.*"

    QUEUE_SARIF_DELIVER_HTTP = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Deliver Sarif - HTTP"
    ROUTEKEY_DELIVER_SARIF_HTTP = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH_DELIVER_HTTP}.*"

    QUEUE_SARIF_DELIVER_AMQP = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Deliver Sarif - AMQP"
    ROUTEKEY_DELIVER_SARIF_AMQP = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH_DELIVER_AMQP}.*"


    class AbstractDeliveryAgent:

        @dataclass_json
        @dataclass(frozen=True)
        class SarifMessage(StampedMessage):
            sarif : Dict
            feedback_context : ScanFeedbackMessage

        async def post_sarif_deliver_msg(self, mq_client : aio_pika.abc.AbstractRobustConnection, log : SarifLog, fb_msg : ScanFeedbackMessage) -> None:
            raise NotImplementedError("post_sarif_deliver_msg")
        
        async def execute_deliver(self, log : SarifLog):
            raise NotImplementedError("execute_deliver")

        
        
    class AmqpDelivery(AMQPClient, AbstractDeliveryAgent):
        def __init__(self, moniker : str, shared_secret : str, *args):
            AMQPClient.__init__(self, *args)
            self.__moniker = moniker
            self.__shared_secret = shared_secret

        async def post_sarif_deliver_msg(self, 
                                         mq_client : aio_pika.abc.AbstractRobustConnection, 
                                         log : SarifLog, 
                                         fb_msg : ScanFeedbackMessage) -> None:
            write_channel = None

            try:
                # Write to the passed MQ since the MQ client implemented in self
                # is where the AMQP Sarif delivery is executed.
                write_channel = await mq_client.channel()
                exchange = await write_channel.get_exchange(CxOneFlowAbstractWorkflowService.EXCHANGE_SCAN_INPUT)

                sarif_msg = PushFeedbackService.AbstractDeliveryAgent.SarifMessage.factory(
                    sarif = json.loads(log.asjson()),
                    feedback_context=fb_msg).to_binary()

                # TODO: gzip the serialized message, add the content-encoding header.
                # TODO: hash the gzipped content.
                alg, hash = gen_signature_header(self.__shared_secret, sarif_msg)


                await exchange.publish(aio_pika.Message(sarif_msg, headers = {alg : hash}, delivery_mode=aio_pika.DeliveryMode.PERSISTENT), 
                                       routing_key=PushFeedbackService.make_topic(ScanStates.FEEDBACK, 
                                       FeedbackWorkflow.PUSH_DELIVER_AMQP, self.__moniker))

            except BaseException as ex:
                pass
            finally:
                if write_channel is not None:
                    await write_channel.close()

    @staticmethod
    def amqp_agent_factory(moniker : str, shared_secret : str, *args) -> AbstractDeliveryAgent:
        return PushFeedbackService.AmqpDelivery(moniker, shared_secret, *args)

    @staticmethod
    def make_topic(state : ScanStates, workflow : FeedbackWorkflow, moniker : str):
        return f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PushFeedbackService.PUSH_TOPIC_PREFIX}{state}.{workflow}.{moniker}"


    def __init__(self, moniker : str, delivery_agents : List[AbstractDeliveryAgent], sarif_opts : ReportOpts, workflow : AbstractFeedbackWorkflow, 
                 amqp_url : str, amqp_user : str, amqp_password : str, ssl_verify : bool):
        super().__init__(amqp_url, amqp_user, amqp_password, ssl_verify)
        self.__sarif_opts = sarif_opts
        self.__service_moniker = moniker
        self.__workflow = workflow
        self.__agents = delivery_agents

    async def execute_sarif_generation(self, msg : aio_pika.abc.AbstractIncomingMessage, cxone_client : CxOneClient):
        fm = await self._safe_deserialize_body(msg, ScanFeedbackMessage)
        push_details = PushDetails.from_dict(fm.workflow_details)

        try:
            if await self.__workflow.is_enabled():
                # Generate Sarif for the scan
                sarif_start = perf_counter_ns()
                sarif_log = await get_sarif_v210_log_for_scan(cxone_client, self.__sarif_opts, fm.scanid, throw_on_run_failure=True,
                                                              clone_url=push_details.clone_url, branch=push_details.source_branch)
                PushFeedbackService.log().debug(f"Sarif log generated in {perf_counter_ns() - sarif_start}ns")


                # TODO: This should be tasks
                for agent in self.__agents:
                    await agent.post_sarif_deliver_msg(await self.mq_client(), sarif_log, fm)

                
                # Get the json for the Sarif
                # Publish messages for delivery, routed by type of delivery topic (amqp/http)
                await msg.ack()
            else:
                await msg.ack()
        except CxOneException as ex:
            PushFeedbackService.log().exception(ex)
            await msg.nack()
        except BaseException as bex:
            PushFeedbackService.log().error("Unrecoverable exception, aborting Sarif generation.")
            PushFeedbackService.log().exception(bex)
            await msg.ack()



    async def start_sarif_feedback(self, projectid : str, scanid : str, details : PushDetails) -> None:
        await self.__workflow.workflow_start(await self.mq_client(), self.__service_moniker, projectid, scanid, **(details.as_dict()))

    async def handle_completed_scan(self, msg : ScanAwaitMessage) -> None:
        if msg.workflow == ScanWorkflow.PUSH:
            await self.__workflow.feedback_start(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, **(msg.workflow_details))
    
    async def handle_awaited_scan_error(self, msg : ScanAwaitMessage, error_msg : str) -> None:
        if msg.workflow == ScanWorkflow.PUSH:
            await self.__workflow.feedback_error(await self.mq_client(), msg.moniker, msg.projectid, msg.scanid, error_msg, **(msg.workflow_details))
