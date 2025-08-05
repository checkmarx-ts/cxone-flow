from workflows.resolver_workflow import ResolverScanningWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging import (
    DelegatedScanMessage,
    DelegatedScanResultMessage,
)
from workflows import ScanStates
from scm_services import SCMService
from cxone_service import CxOneService
from orchestration import AbstractOrchestrator
from typing import Tuple
from .exceptions import ResolverAgentException
import aio_pika, pickle, shutil, subprocess
from .resolver_runner import ResolverRunner, ResolverExecutionContext
from pathlib import Path
from _version import __version__


class ResolverRunnerAgent(BaseWorkflowService):

    def __init__(
        self,
        tag: str,
        public_key: bytearray,
        resolver_runner: ResolverRunner,
        amqp_args: Tuple,
    ):
        super().__init__(*amqp_args)
        self.__tag = tag
        self.__public_key = public_key
        self.__resolver_runner = resolver_runner

    @property
    def tag(self) -> str:
        return self.__tag

    @property
    def route_key(self) -> str:
        return f"{ResolverScanService.ROUTEKEY_RESOLVER_RESULT_STUB}.{self.__tag}"

    async def __send_failure_response(
        self,
        workflow: ResolverScanningWorkflow,
        scan_msg: DelegatedScanMessage,
        resolver_exit_code: int = None,
        logs: bytearray = None,
    ) -> None:
        result_msg = DelegatedScanResultMessage.factory(
            moniker=scan_msg.moniker,
            state=ScanStates.FAILURE,
            workflow=scan_msg.workflow,
            details=scan_msg.details,
            details_signature=scan_msg.details_signature,
            resolver_exit_code=resolver_exit_code,
            logs=logs,
        )

        await workflow.deliver_delegated_scan_outcome(
            await self.mq_client(),
            self.route_key,
            result_msg,
            ResolverScanService.EXCHANGE_RESOLVER_SCAN,
        )

    def __msg_should_process(self, msg : DelegatedScanMessage, runner : ResolverExecutionContext) -> bool:
            if not runner.can_execute:
                ResolverRunnerAgent.log().error(
                    "The runner instance indicates it can't run."
                )
                return False
            
            return True


    async def __call__(self, msg: aio_pika.abc.AbstractIncomingMessage):
        scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)
        try:
            async with await self.__resolver_runner.executor() as runner:

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
                elif not self.__msg_should_process(scan_msg, runner):
                    await self.__send_failure_response(workflow, scan_msg)
                else:

                    # Unpickle the SCMService instance and clone
                    scm_service = pickle.loads(scan_msg.details.pickled_scm_service)
                    if not isinstance(scm_service, SCMService):
                        raise ResolverAgentException.type_mismatch_exception(SCMService, type(scm_service))
                    
                    # Unpickle CxOneService
                    cxone_service = pickle.loads(scan_msg.details.pickled_cxone_service)
                    if not isinstance(cxone_service, CxOneService):
                        raise ResolverAgentException.type_mismatch_exception(CxOneService, type(cxone_service))

                    project_config = await cxone_service.load_project_config_by_id(scan_msg.details.project_id)


                    ResolverRunnerAgent.log().info(f"Agent processing: Project: [{project_config.name}]" + 
                                                    f" From: [{scan_msg.moniker}] Workflow: [{str(scan_msg.workflow)}]" + 
                                                    f" Clone: [{scan_msg.details.clone_url}@{scan_msg.details.commit_hash}] CorId: [{scan_msg.correlation_id}]")

                    async with await scm_service.cloner.clone(
                        scan_msg.details.clone_url,
                        scan_msg.details.event_context,
                        False,
                        runner.clone_path.rstrip("/") + "/",
                        False,
                    ) as clone_worker:
                        cloned_repo_loc = Path(await clone_worker.loc())
                        await scm_service.cloner.reset_head(
                            cloned_repo_loc, scan_msg.details.commit_hash
                        )

                        resolver_exec_result = await runner.execute_resolver(project_config.name, scan_msg.details.file_filters)

                        resolver_res_path = Path(runner.result_resolver_out_file_path)
                        if resolver_res_path.exists() and resolver_res_path.is_file():
                            shutil.copyfile(resolver_res_path, cloned_repo_loc / ".cxsca-results.json" )

                        container_res_path = Path(runner.result_container_out_file_path)
                        if container_res_path.exists() and container_res_path.is_file():
                            shutil.copyfile(container_res_path, cloned_repo_loc / ".cxsca-container-results.json" )

                        resolver_run_logs = resolver_exec_result.stdout
                        return_code = resolver_exec_result.returncode


                        # Scan the resulting repo.
                        inspector, _ = await AbstractOrchestrator.exec_local_scan(
                            cloned_repo_loc, cxone_service, 
                            f"{scan_msg.details.clone_url}|{scan_msg.details.scan_branch}|{scan_msg.details.commit_hash}|CorId:{scan_msg.correlation_id}",
                            scan_msg.details.scan_branch, project_config, scan_msg.details.scan_tags | {"resolver" : "success" if return_code == 0 else "failure"})

                        result_msg = DelegatedScanResultMessage.factory(
                            moniker=scan_msg.moniker,
                            state=ScanStates.DONE if return_code == 0 else ScanStates.FAILURE,
                            workflow=scan_msg.workflow,
                            details=scan_msg.details,
                            details_signature=scan_msg.details_signature,
                            logs=resolver_run_logs,
                            scan_id=inspector.scan_id,
                            resolver_exit_code = return_code
                        )

                        await workflow.deliver_delegated_scan_outcome(
                            await self.mq_client(),
                            self.route_key,
                            result_msg,
                            ResolverScanService.EXCHANGE_RESOLVER_SCAN,
                        )
        except subprocess.CalledProcessError as cpex:
            ResolverRunnerAgent.log().error(f"Resolver workflow failure for CorId: [{scan_msg.correlation_id}]")
            ResolverRunnerAgent.log().exception(cpex)
            await self.__send_failure_response(
                workflow, scan_msg, cpex.returncode, cpex.output
            )
            await msg.nack(requeue=False)
        except BaseException as ex:
            ResolverRunnerAgent.log().exception(f"Resolver workflow failure for CorId: [{scan_msg.correlation_id}]", ex)
            await self.__send_failure_response(workflow, scan_msg)
            await msg.nack(requeue=False)
        else:
            ResolverRunnerAgent.log().info(f"Resolver workflow completed successfully for CorId: [{scan_msg.correlation_id}]")
            await msg.ack()
