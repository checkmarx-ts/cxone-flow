from ..scan_message import ScanMessage
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanAnnotationMessage(ScanMessage):
    annotation : str
    schema: str = "v1"

