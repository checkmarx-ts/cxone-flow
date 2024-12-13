from workflows.resolver_workflow import ResolverScanningWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging.v1.delegated_scan import (
    DelegatedScanMessage,
    DelegatedScanResultMessage,
)
from workflows import ScanStates
from scm_services.cloner import Cloner
from typing import Tuple
from .exceptions import ResolverAgentException
import aio_pika, pickle, gzip, os, subprocess, tempfile
from .resolver_runner import ResolverRunner
from _version import __version__


class ResolverRunnerAgent(BaseWorkflowService):

    def __init__(
        self,
        tag: str,
        public_key: bytearray,
        runner: ResolverRunner,
        amqp_args: Tuple,
    ):
        super().__init__(*amqp_args)
        self.__tag = tag
        self.__public_key = public_key
        self.__runner = runner

    @property
    def tag(self) -> str:
        return self.__tag

    @property
    def route_key(self) -> str:
        return f"{BaseWorkflowService.TOPIC_PREFIX}{ResolverScanService.RESOLVER_TOPIC_PREFIX}exec.sca-resolver.scan-complete.{self.__tag}"

    async def __send_failure_response(
        self,
        workflow: ResolverScanningWorkflow,
        scan_msg: DelegatedScanMessage,
        exit_code: int = None,
        logs: bytearray = None,
    ) -> None:
        result_msg = DelegatedScanResultMessage.factory(
            moniker=scan_msg.moniker,
            state=ScanStates.FAILURE,
            workflow=scan_msg.workflow,
            details=scan_msg.details,
            details_signature=scan_msg.details_signature,
            resolver_results=None,
            container_results=None,
            exit_code=exit_code,
            logs=logs,
        )

        await workflow.deliver_resolver_results(
            await self.mq_client(),
            self.route_key,
            result_msg,
            ResolverScanService.EXCHANGE_RESOLVER_SCAN,
        )

    def __msg_should_process(self, msg : DelegatedScanMessage) -> bool:
            if not __version__ == msg.details.cxoneflow_version:
                ResolverRunnerAgent.log().error(
                    f"Agent version {__version__} mismatch: Scan request coming from server version {msg.details.cxoneflow_version}."
                )
                return False
    
            if not self.__runner.can_execute:
                ResolverRunnerAgent.log().error(
                    "The runner instance indicates it can't run."
                )
                return False
            
            return True


    async def __call__(self, msg: aio_pika.abc.AbstractIncomingMessage):
        scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)
        try:
            async with self.__runner:

                ResolverRunnerAgent.log().debug("Message received")

                workflow = ResolverScanningWorkflow.from_public_key(
                    scan_msg.capture_logs, self.__public_key
                )

                if not workflow.validate_signature(
                    scan_msg.details_signature, scan_msg.details.to_binary()
                ):
                    ResolverRunnerAgent.log().error(
                        f"Signature validation failed for tag {self.__tag} coming from service moniker {scan_msg.moniker}."
                    )
                elif not self.__msg_should_process(scan_msg):
                    await self.__send_failure_response(workflow, scan_msg)
                else:

                    # Unpickle the cloner and clone
                    cloner = pickle.loads(scan_msg.details.pickled_cloner)

                    if not isinstance(cloner, Cloner):
                        raise ResolverAgentException.cloner_type_exception(type(cloner))
                    else:
                        async with await cloner.clone(
                            scan_msg.details.clone_url,
                            scan_msg.details.event_context,
                            False,
                            self.__runner.clone_path,
                        ) as clone_worker:
                            cloned_repo = await clone_worker.loc()
                            await cloner.reset_head(
                                cloned_repo, scan_msg.details.commit_hash
                            )

                            resolver_exec_result = await self.__runner.execute_resolver(scan_msg.details.project_name)

                            with open(self.__runner.resolver_out_file, "rt") as f:
                                sca_results = gzip.compress(bytes(f.read(), "UTF-8"))

                            with open(self.__runner.container_out_file, "rt") as f:
                                container_results = gzip.compress(bytes(f.read(), "UTF-8"))

                            resolver_run_logs = resolver_exec_result.stdout
                            return_code = resolver_exec_result.returncode

                            result_msg = DelegatedScanResultMessage.factory(
                                moniker=scan_msg.moniker,
                                state=ScanStates.DONE,
                                workflow=scan_msg.workflow,
                                details=scan_msg.details,
                                details_signature=scan_msg.details_signature,
                                resolver_results=sca_results,
                                container_results=container_results,
                                logs=resolver_run_logs,
                                exit_code=return_code,
                            )

                            await workflow.deliver_resolver_results(
                                await self.mq_client(),
                                self.route_key,
                                result_msg,
                                ResolverScanService.EXCHANGE_RESOLVER_SCAN,
                            )
        except subprocess.CalledProcessError as cpex:
            self.log().exception(cpex.output.decode(), cpex)
            await self.__send_failure_response(
                workflow, scan_msg, cpex.returncode, cpex.output
            )
            await msg.nack(requeue=False)
        except BaseException as ex:
            self.log().exception(ex)
            await self.__send_failure_response(workflow, scan_msg)
            await msg.nack(requeue=False)
        else:
            await msg.ack()
