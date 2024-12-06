from .base_message import StampedMessage
from dataclasses import dataclass
from .. import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanHeader(StampedMessage):
    moniker: str
    state: ScanStates
    workflow: ScanWorkflow

@dataclass(frozen=True)
class ScanMessage(ScanHeader):
    scanid: str
    projectid : str
    workflow_details : dict

