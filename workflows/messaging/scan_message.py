from .base_message import StampedMessage
from dataclasses import dataclass
from workflows.enums import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanHeader(StampedMessage):
    moniker: str
    state: ScanStates
    workflow: ScanWorkflow

@dataclass(frozen=True)
class ScanWorkflowHeader(ScanHeader):
    workflow_details : dict
    
@dataclass(frozen=True)
class ScanMessage(ScanWorkflowHeader):
    scanid: str
    projectid : str

