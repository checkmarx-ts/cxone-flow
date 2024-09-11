"""
This is a Flask entrypoint for receiving webhook payloads and dispatching them to the proper
orchestrator.  Code here should be limited to receive and delegating the logic to the
proper orchestrator.  This allows this to be replaced with a different type of endpoint handler
that is compatible with other methods of deployment.
"""
from _agent import __agent__
from flask import Flask, request, Response, send_from_directory
from orchestration import OrchestrationDispatch, BitBucketDataCenterOrchestrator, AzureDevOpsEnterpriseOrchestrator
import json, logging, asyncio, os
from config import CxOneFlowConfig, ConfigurationException, get_config_path
from time import perf_counter_ns
from task_management import TaskManager
import cxoneflow_logging as cof_logging

cof_logging.bootstrap()

__app_name__ = __agent__

__log = logging.getLogger(__app_name__)

try:
    CxOneFlowConfig.bootstrap(get_config_path())
except ConfigurationException as ce:
    __log.exception(ce)
    raise

TaskManager.bootstrap()


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
        TaskManager.in_background(OrchestrationDispatch.execute(BitBucketDataCenterOrchestrator(request.headers, request.data)))
        return Response(status=204)
    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)

  
@app.post("/adoe")
async def adoe_webhook_endpoint():
    __log.info("Received hook for Azure DevOps Enterprise")
    __log.debug(f"adoe webhook: headers: [{request.headers}] body: [{json.dumps(request.json)}]")
    try:
        orch = AzureDevOpsEnterpriseOrchestrator(request.headers, request.data);

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
    
@app.get("/artifacts/<path:path>" )
async def artifacts(path):
    __log.debug(f"Fetching artifact at {path}")
    return send_from_directory("artifacts", path)
