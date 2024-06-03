from ..scan_message import ScanMessage
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanFeedbackMessage(ScanMessage):
    schema: str = "v1"

