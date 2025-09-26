import aio_pika, gzip, asyncio, json, requests, logging
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
from typing import List, Dict, Union, Any, Tuple

class PushFeedbackService(CxOneFlowAbstractWorkflowService):
    PUSH_ELEMENT_PREFIX = "push:"
    PUSH_TOPIC_PREFIX = "push."

    EXCHANGE_SARIF_WORK = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Sarif Workflows"

    QUEUE_SARIF_GEN = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PUSH_ELEMENT_PREFIX}Generate Sarif"
    ROUTEKEY_GEN_SARIF = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PUSH_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PUSH_GEN}.*"


    class AbstractDeliveryAgent:
        @classmethod
        def log(clazz):
            return logging.getLogger(clazz.__name__)

        @staticmethod
        def _gen_signature_headers(secret : str, content : Any) -> Dict[str, str]:
            alg, hash = gen_signature_header(secret, content)
            return {"x-cx-signature-alg" : alg, "x-cx-signature": hash}

        async def execute_sarif_delivery(self, log : SarifLog, msg_headers : Dict) -> None:
            raise NotImplementedError("execute_sarif_delivery")

        async def execute_sarif_error_delivery(self, msg : str, msg_headers : Dict) -> None:
            raise NotImplementedError("execute_sarif_error_delivery")
        
    class AbstractMessageDeliveryAgent(AbstractDeliveryAgent):
        def __init__(self, shared_secret : str):
            self.__shared_secret = shared_secret

        def package_message(self, msg : bytes) -> Tuple[bytes, Dict[str,str]]:
            compressed_msg = gzip.compress(msg)
            headers = {"content-encoding" : "gzip"}
            headers.update(PushFeedbackService.AbstractDeliveryAgent._gen_signature_headers(self.__shared_secret, compressed_msg))
            return compressed_msg, headers

        
        
    class AmqpDeliveryAgent(AMQPClient, AbstractMessageDeliveryAgent):
        def __init__(self, moniker : str, 
                     shared_secret : str, 
                     exchange : str, 
                     topic_prefix : str,
                     topic_suffix : str,
                     *args):
            PushFeedbackService.AbstractMessageDeliveryAgent.__init__(self, shared_secret)
            AMQPClient.__init__(self, *args)
            self.__moniker = moniker
            self.__dest_exchange = exchange
            self.__topic_prefix = topic_prefix
            self.__topic_suffix = topic_suffix

        def __get_topic(self):
            topic = ""
            if self.__topic_prefix is not None:
                topic += self.__topic_prefix.rstrip(".") + "."
            
            topic += self.__moniker

            if self.__topic_suffix is not None:
                topic += "." + self.__topic_suffix.lstrip(".")
            
            return topic


        async def __publish_message(self, msg : bytes, headers : Dict):
            write_channel = None

            try:
                write_channel = await (await self.mq_client()).channel()
                exchange = await write_channel.get_exchange(self.__dest_exchange)

                pub_result = await exchange.publish(aio_pika.Message(msg, headers = headers, delivery_mode=aio_pika.DeliveryMode.PERSISTENT), 
                                       routing_key=self.__get_topic())
                
                self.log().debug("Msg published for %s on exchange %s result: %s", self.__moniker, self.__dest_exchange, pub_result)
            except BaseException:
                PushFeedbackService.log().exception("Sarif AMQP delivery failed.")
            finally:
                if write_channel is not None:
                    await write_channel.close()

        async def __pack_and_publish(self, msg : bytes, msg_headers):
            packaged_msg, packaged_headers = self.package_message(msg)
            packaged_headers.update(msg_headers)
            await self.__publish_message(packaged_msg, packaged_headers)

        async def execute_sarif_delivery(self, log : SarifLog, msg_headers : Dict) -> None:
            await self.__pack_and_publish(log.asjson().encode("UTF-8"), msg_headers)

        async def execute_sarif_error_delivery(self, msg : str, msg_headers : Dict) -> None:
            await self.__pack_and_publish(json.dumps({"error" : msg}).encode('UTF-8'), msg_headers)

    class HttpDeliveryAgent(AbstractMessageDeliveryAgent):

        def __init__(self, shared_secret : str, endpoint_url : str, 
                     delivery_retries : int, delivery_retry_delay_s : int, proxies : Dict[str, str], ssl_verify : Union[bool, str]):
            super().__init__(shared_secret)
            self.__url = endpoint_url
            self.__retries = delivery_retries
            self.__delay = delivery_retry_delay_s
            self.__proxies = proxies
            self.__ssl_verify = ssl_verify

        async def __post(self, msg : bytes, headers : Dict):
            remaining = max(self.__retries, 0)

            once = False
            delivered = False
            while remaining >= 0:
                try:
                    if once:
                        PushFeedbackService.HttpDeliveryAgent.log().warning(f"Delaying before retring delivery to {self.__url}. Retries remaining: {remaining}")
                        await asyncio.sleep(self.__delay)                    

                    response = await asyncio.to_thread(requests.post, url=self.__url, data=msg, headers=headers, proxies=self.__proxies, verify=self.__ssl_verify)
                    PushFeedbackService.HttpDeliveryAgent.log().info(f"Posted Sarif log to {self.__url} with response {response.status_code}")

                    if response.ok:
                        delivered = True
                        break
                except BaseException as bex:
                    PushFeedbackService.HttpDeliveryAgent.log().exception(bex)
                    break
                finally:
                    remaining -= 1
                    once = True
            
            if not delivered:
                PushFeedbackService.HttpDeliveryAgent.log().error(f"Delivery of Sarif log to {self.__url} failed!")


        async def execute_sarif_delivery(self, log : SarifLog, msg_headers : Dict) -> None:
            packaged_msg, packaged_headers = self.package_message(log.asjson().encode("UTF-8"))
            packaged_headers.update(msg_headers)
            await self.__post(packaged_msg, packaged_headers)

        async def execute_sarif_error_delivery(self, msg : str, msg_headers : Dict) -> None:
            packaged_msg, packaged_headers = self.package_message(json.dumps({"error" : msg}).encode('UTF-8'))
            packaged_headers.update(msg_headers)
            await self.__post(packaged_msg, packaged_headers)


    @staticmethod
    def make_topic(state : ScanStates, workflow : FeedbackWorkflow, moniker : str):
        return f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PushFeedbackService.PUSH_TOPIC_PREFIX}{state}.{workflow}.{moniker}"


    def __init__(self, moniker : str, 
                 delivery_agents : List[AbstractDeliveryAgent], 
                 sarif_opts : ReportOpts, 
                 workflow : AbstractFeedbackWorkflow, 
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

                headers = {
                    "x-cx-scanid" : fm.scanid,
                    "x-cx-projectid" : fm.projectid,
                    "x-cx-service" : fm.moniker,
                    "x-cx-clone-url" : push_details.clone_url,
                    "x-cx-branch" : push_details.source_branch,
                    "x-cx-commit" : push_details.commit_hash,
                    "x-cx-is-error" : str(fm.is_error)
                }

                # Generate Sarif for the scan
                if not fm.is_error:
                    sarif_start = perf_counter_ns()
                    sarif_log = await get_sarif_v210_log_for_scan(cxone_client, 
                                                                self.__sarif_opts, 
                                                                fm.scanid, 
                                                                throw_on_run_failure=True,
                                                                clone_url=push_details.clone_url, 
                                                                branch=push_details.source_branch)
                    
                    PushFeedbackService.log().debug(f"Sarif log generated in {perf_counter_ns() - sarif_start}ns")

                    # Post the message for delivery
                    await asyncio.wait([asyncio.create_task(agent.execute_sarif_delivery(sarif_log, headers)) for agent in self.__agents])
                else:
                    await asyncio.wait([asyncio.create_task(agent.execute_sarif_error_delivery(fm.error_msg, headers)) for agent in self.__agents])
                
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
