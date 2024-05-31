from .. import ScanMessage
from dataclasses import dataclass
from ...state_service import WorkflowStateService

@dataclass(frozen=True)
class ScanAwaitMessage(ScanMessage):
    state: WorkflowStateService.ScanStates
    workflow: WorkflowStateService.ScanWorkflow
    schema: str = "v1"

