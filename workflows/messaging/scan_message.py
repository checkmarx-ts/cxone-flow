from .base_message import BaseMessage
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanMessage(BaseMessage):
    scanid: str

