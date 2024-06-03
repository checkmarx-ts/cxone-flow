from ..scan_message import ScanMessage
from dataclasses import dataclass
from ... import ScanStates, ScanWorkflow

@dataclass(frozen=True)
class ScanAwaitMessage(ScanMessage):
    state: ScanStates
    workflow: ScanWorkflow
    schema: str = "v1"


