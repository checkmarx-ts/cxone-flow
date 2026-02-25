from workflows.messaging.scan_message import ScanMessage, ScanWorkflowHeader
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanAnnotationMessage(ScanMessage):
    annotation : str

@dataclass(frozen=True)
class PreScanAnnotationMessage(ScanWorkflowHeader):
    annotation : str
