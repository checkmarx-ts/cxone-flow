from .base_message import BaseMessage
from dataclasses import dataclass
from .. import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanMessage(BaseMessage):
    scanid: str
    state: ScanStates
    workflow: ScanWorkflow

