from workflows import CxOneFlowAbstractWorkflowService
from workflows.enums import ScanStates, FeedbackWorkflow

class PRQueueConstants:
    PR_ELEMENT_PREFIX = "pr:"
    PR_TOPIC_PREFIX = "pr."

    EXCHANGE_SCAN_INPUT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan In"
    EXCHANGE_SCAN_WAIT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Await"
    EXCHANGE_SCAN_POLLING_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Polling Delivery"


    EXCHANGE_SCAN_ANNOTATE = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Annotate"
    EXCHANGE_SCAN_FEEDBACK = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Scan Feedback"

    QUEUE_SCAN_POLLING_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Polling Scans"
    QUEUE_SCAN_WAIT_LEGACY = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}Awaited Scans"


    QUEUE_ANNOTATE_PR = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}PR Annotating"
    QUEUE_FEEDBACK_PR = f"{CxOneFlowAbstractWorkflowService.ELEMENT_PREFIX}{PR_ELEMENT_PREFIX}PR Feedback"
    
    ROUTEKEY_POLL_BINDING_LEGACY = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.AWAIT}.*.*"


    ROUTEKEY_FEEDBACK_PR = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.FEEDBACK}.{FeedbackWorkflow.PR}.*"
    ROUTEKEY_ANNOTATE_PR = f"{CxOneFlowAbstractWorkflowService.TOPIC_PREFIX}{PR_TOPIC_PREFIX}{ScanStates.ANNOTATE}.{FeedbackWorkflow.PR}.*"
