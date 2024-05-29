"""
This is a Flask entrypoint for receiving webhook payloads and dispatching them to the proper
orchestrator.  Code here should be limited to receive and delegating the logic to the
proper orchestrator.  This allows this to be replaced with a different type of endpoint handler
that is compatible with other methods of deployment.
"""
from _agent import __agent__
from flask import Flask, request, Response
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

@app.get("/ping")
async def ping():
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
        TaskManager.in_background(OrchestrationDispatch.execute(AzureDevOpsEnterpriseOrchestrator(request.headers, request.data)))
        return Response(status=204)
    except Exception as ex:
        __log.exception(ex)
        return Response(status=400)
    
