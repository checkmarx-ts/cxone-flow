from ..scan_message import ScanHeader
from ..base_message import BaseMessage
from dataclasses import dataclass
from api_utils.auth_factories import EventContext
from typing import Dict

@dataclass(frozen=True)
class DelegatedScanDetails(ScanHeader):
    clone_url : str
    pickled_cloner : bytearray
    event_context : EventContext
    container_tag : str = None
    schema: str = "v1"

@dataclass(frozen=True)
class DelegatedScanMessage(BaseMessage):
    details : DelegatedScanDetails
    details_signature : str
    emit_logs : bool
    schema: str = "v1"

