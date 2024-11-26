from ..scan_message import ScanHeader
from dataclasses import dataclass
from api_utils.auth_factories import EventContext
from typing import Dict


@dataclass(frozen=True)
class DelegatedScanMessage(ScanHeader):
    clone_url : str
    event_context : EventContext
    additional_args : Dict
    emit_logs : bool
    schema: str = "v1"
