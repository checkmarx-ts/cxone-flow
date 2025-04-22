"""
This is a Flask entrypoint for receiving webhook payloads and dispatching them to the proper
orchestrator.  Code here should be limited to receive and delegating the logic to the
proper orchestrator.  This allows this to be replaced with a different type of endpoint handler
that is compatible with other methods of deployment.
"""
from _agent import __agent__
from flask import Flask, request, Response, send_from_directory
from orchestration import OrchestrationDispatch

from orchestration.kickoff import KickoffOrchestrator
from orchestration.kickoff.bbdc import BitBucketDataCenterKickoffOrchestrator
from orchestration.kickoff.gh import GithubKickoffOrchestrator
from orchestration.kickoff.adoe import AzureDevOpsKickoffOrchestrator
from orchestration.kickoff.gl import GitlabKickoffOrchestrator

from orchestration.bbdc import  BitBucketDataCenterOrchestrator
from orchestration.adoe import AzureDevOpsEnterpriseOrchestrator
from orchestration.gh import GithubOrchestrator
from orchestration.gl import GitlabOrchestrator

import json, logging, os, asyncio
from config import ConfigurationException, RouteNotFoundException, get_config_path
from config.server import CxOneFlowConfig
from task_management import TaskManager
import cxoneflow_logging as cof_logging
from api_utils.auth_factories import EventContext, HeaderFilteredEventContext
import cxoneflow_kickoff_api as ko
import cxoneflow_kickoff_api.status as kostat

TaskManager.bootstrap()
asyncio.set_event_loop(TaskManager.loop())

cof_logging.bootstrap()

__app_name__ = __agent__

__log = logging.getLogger(__app_name__)

try:
    CxOneFlowConfig.bootstrap(get_config_path())
except ConfigurationException as ce:
    __log.exception(ce)
    raise

async def __kickoff_impl(orch : KickoffOrchestrator):
    msg = None
    code = kostat.KickoffStatusCodes.SERVER_ERROR

    try:
        if await OrchestrationDispatch.execute_kickoff(orch):
            code = kostat.KickoffStatusCodes.SCAN_STARTED
            msg = ko.KickoffResponseMsg(running_scans=orch.running_scans, started_scan=orch.started_scan)
        else:
            code = kostat.KickoffStatusCodes.BAD_REQUEST
            msg = None
    except KickoffOrchestrator.KickoffScanExistsException:
        code = kostat.KickoffStatusCodes.SCAN_EXISTS
        msg = ko.KickoffResponseMsg(running_scans=orch.running_scans)
    except KickoffOrchestrator.TooManyRunningScansExeception:
        code = kostat.KickoffStatusCodes.TOO_MANY_SCANS
        msg = ko.KickoffResponseMsg(running_scans=orch.running_scans)
    except RouteNotFoundException:
        code = kostat.KickoffStatusCodes.NO_ROUTE
        msg = None
    except OrchestrationDispatch.NotAuthorizedException:
        code = kostat.KickoffStatusCodes.NOT_AUTHORIZED
        msg = None

    # pylint: disable=E1101
    return Response(msg.to_json() if msg is not None else None, status=code.value, content_type="application/json")


app = Flask(__app_name__)

@app.route("/ping", methods=['GET', 'POST'])
async def ping():
    if request.method != "GET" and "ENABLE_DUMP" in os.environ.keys():
        content = json.dumps(request.json) if request.content_type == "application/json" else request.data
        __log.debug(f"ping webhook: headers: [{request.headers}] body: [{content}]")

    return Response("pong", status=200)

@app.post("/bbdc")
async def bbdc_webhook_endpoint():
    __log.info("Received hook for BitBucket Data Center")
    __log.debug(f"bbdc webhook: headers: [{request.headers}] body: [{json.dumps(request.json)}]")
    try:
        TaskManager.in_background(OrchestrationDispatch.execute(BitBucketDataCenterOrchestrator(EventContext(request.get_data(), dict(request.headers)))))
        return Response(status=204)
    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)
    

@app.post("/bbdc/kickoff")
async def bbdc_kickoff_endpoint():
    ec = EventContext(request.get_data(), dict(request.headers))
    return await TaskManager.in_foreground(__kickoff_impl(BitBucketDataCenterKickoffOrchestrator(ko.BitbucketKickoffMsg(**(ec.message)), ec)))

@app.post("/gh")
async def github_webhook_endpoint():
    __log.info("Received hook for Github")
    __log.debug(f"github webhook: headers: [{request.headers}] body: [{json.dumps(request.json)}]")
    try:
        orch = GithubOrchestrator(HeaderFilteredEventContext(request.get_data(), dict(request.headers), "User-Agent|X-(Git)?[H|h]ub"))

        if not orch.is_diagnostic:
            TaskManager.in_background(OrchestrationDispatch.execute(orch))
            return Response(status=204)
        else:
            # The ping has no route URL associated, so check if any route matches.
            for service in CxOneFlowConfig.retrieve_scm_services(orch.config_key):
                if await orch.is_signature_valid(service.shared_secret):
                    return Response(status=200)
            return Response(status=401)

    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)

@app.post("/gh/kickoff")
async def github_kickoff_endpoint():
    ec = EventContext(request.get_data(), dict(request.headers))
    return await TaskManager.in_foreground(__kickoff_impl(GithubKickoffOrchestrator(ko.GithubKickoffMsg(**(ec.message)), ec)))


@app.post("/adoe")
async def adoe_webhook_endpoint():
    __log.info("Received hook for Azure DevOps Enterprise")
    __log.debug(f"adoe webhook: headers: [{request.headers}] body: [{json.dumps(request.json)}]")
    try:
        orch = AzureDevOpsEnterpriseOrchestrator(EventContext(request.get_data(), dict(request.headers)))

        if not orch.is_diagnostic:
            TaskManager.in_background(OrchestrationDispatch.execute(orch))
            return Response(status=204)
        else:
            # ADO's test payload can't be matched against a route since it is "fabrikammed". 
            # Test all the services to see if any use the shared secret.
            for service in CxOneFlowConfig.retrieve_scm_services(orch.config_key):
                if await orch.is_signature_valid(service.shared_secret):
                    return Response(status=200)
            return Response(status=401)
    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)


@app.post("/adoe/kickoff")
async def adoe_kickoff_endpoint():
    ec = EventContext(request.get_data(), dict(request.headers))
    return await TaskManager.in_foreground(__kickoff_impl(AzureDevOpsKickoffOrchestrator(ko.AdoKickoffMsg(**(ec.message)), ec)))

@app.post("/gl")
async def gitlab_webhook_endpoint():
    __log.info("Received hook for GitLab")
    __log.debug(f"gitlab webhook: headers: [{request.headers}] body: [{json.dumps(request.json)}]")
    try:
        orch = GitlabOrchestrator(HeaderFilteredEventContext(request.get_data(), dict(request.headers), "User-Agent|X-Gitlab|Idempotency-Key"))

        if not orch.is_diagnostic:
            TaskManager.in_background(OrchestrationDispatch.execute(orch))
            return Response(status=201)
        else:
            for service in CxOneFlowConfig.retrieve_scm_services(orch.config_key):
                if await orch.is_signature_valid(service.shared_secret):
                    return Response(status=200)
            return Response(status=401)
    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)

@app.post("/gl/kickoff")
async def gitlab_kickoff_endpoint():
    ec = EventContext(request.get_data(), dict(request.headers))
    return await TaskManager.in_foreground(__kickoff_impl(GitlabKickoffOrchestrator(ko.GitlabKickoffMsg(**(ec.message)), ec)))


@app.get("/artifacts/<path:path>" )
async def artifacts(path):
    __log.debug(f"Fetching artifact at {path}")
    return send_from_directory("artifacts", path)
