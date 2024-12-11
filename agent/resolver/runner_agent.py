from workflows.resolver_workflow import ResolverScanningWorkflow
from workflows.base_service import BaseWorkflowService
from workflows.resolver_scan_service import ResolverScanService
from workflows.messaging.v1.delegated_scan import (
    DelegatedScanMessage,
    DelegatedScanResultMessage,
)
from workflows import ScanStates
from scm_services.cloner import Cloner
from typing import Tuple, List
from .exceptions import ResolverAgentException
import aio_pika, pickle, gzip, os, subprocess, asyncio, tempfile
from .resolver_opts import ResolverOpts
from _version import __version__


class ResolverRunnerAgent(BaseWorkflowService):

    __resolver_name = "ScaResolver"

    def __init__(
        self,
        tag: str,
        public_key: bytearray,
        opts: ResolverOpts,
        toolkit_path: str,
        resolver_work_path: str,
        resolver_path: str,
        amqp_args: Tuple,
    ):
        super().__init__(*amqp_args)
        self.__tag = tag
        self.__public_key = public_key
        self.__resolver_opts = opts
        self.__toolkit_path = toolkit_path
        self.__resolver_path = resolver_path
        self.__resolver_work_path = resolver_work_path.rstrip("/") + "/"

    @property
    def tag(self) -> str:
        return self.__tag

    @property
    def route_key(self) -> str:
        return f"exec.sca-resolver.scan-complete.{self.__tag}"

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

    def __get_resolver_exec_cmd(self) -> List[str]:
        cmd = None

        if self.__resolver_path is not None and (
            os.path.exists(self.__resolver_path)
            and os.path.isfile(self.__resolver_path)
        ):
            cmd = [self.__resolver_path]
        elif os.path.exists(ResolverRunnerAgent.__resolver_name):
            cmd = [ResolverRunnerAgent.__resolver_name]

        return cmd

    async def __call__(self, msg: aio_pika.abc.AbstractIncomingMessage):
        scan_msg = await self._safe_deserialize_body(msg, DelegatedScanMessage)
        try:
            work_loc = tempfile.TemporaryDirectory(
                delete=False, prefix=self.__resolver_work_path
            )
            clone_loc = f"{work_loc.name.rstrip("/")}/clone/"
            os.mkdir(clone_loc)
            resolver_out_loc = f"{work_loc.name.rstrip("/")}/resolver"
            os.mkdir(resolver_out_loc)
            resolver_out_file = f"{resolver_out_loc}/resolver.json"
            container_out_loc = f"{work_loc.name.rstrip("/")}/container"
            os.mkdir(container_out_loc)
            container_out_file = f"{container_out_loc}/container.json"

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
            elif not __version__ == scan_msg.details.cxoneflow_version:
                ResolverRunnerAgent.log().error(
                    f"Agent version {__version__} mismatch: Scan request coming from server version {scan_msg.details.cxoneflow_version}."
                )
                await self.__send_failure_response(workflow, scan_msg)
            elif self.__get_resolver_exec_cmd() is None:
                ResolverRunnerAgent.log().error(
                    f"Could not create the command to run {ResolverRunnerAgent.__resolver_name}."
                )
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
                        clone_loc,
                    ) as clone_worker:
                        cloned_repo = await clone_worker.loc()
                        await cloner.reset_head(
                            cloned_repo, scan_msg.details.commit_hash
                        )
                        cmd = (
                            self.__get_resolver_exec_cmd()
                            + ["offline"]
                            + self.__resolver_opts.as_args()
                        )

                        opts = [
                            "--scan-path",
                            cloned_repo,
                            "--containers-result-path",
                            container_out_file,
                            "--resolver-result-path",
                            resolver_out_file,
                            "--project-name",
                            scan_msg.details.project_name,
                        ]

                        ResolverRunnerAgent.log().debug(
                            f"Running resolver: {cmd + opts}"
                        )

                        resolver_exec_result = await asyncio.to_thread(
                            subprocess.run,
                            cmd + opts,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            check=True,
                        )

                        ResolverRunnerAgent.log().debug(
                            f"Resolver finished: {resolver_exec_result}"
                        )

                        with open(resolver_out_file, "rt") as f:
                            sca_results = gzip.compress(bytes(f.read(), "UTF-8"))

                        with open(container_out_file, "rt") as f:
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
        finally:
            work_loc.cleanup()
