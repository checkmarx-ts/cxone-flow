from .base_message import BaseMessage
from dataclasses import dataclass
from .. import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanHeader(BaseMessage):
    moniker: str
    state: ScanStates
    workflow: ScanWorkflow

@dataclass(frozen=True)
class ScanMessage(ScanHeader):
    scanid: str
    projectid : str
    workflow_details : dict

