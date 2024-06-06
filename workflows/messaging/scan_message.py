from .base_message import BaseMessage
from dataclasses import dataclass
from .. import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanMessage(BaseMessage):
    moniker: str
    scanid: str
    projectid : str
    state: ScanStates
    workflow: ScanWorkflow
    workflow_details : dict

