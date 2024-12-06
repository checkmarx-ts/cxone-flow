from ..scan_message import ScanHeader
from ..base_message import BaseMessage
from dataclasses import dataclass
from api_utils.auth_factories import EventContext
from typing import Optional

@dataclass(frozen=True)
class DelegatedScanDetails(BaseMessage):
    clone_url : str
    commit_hash : str
    file_filters : str
    project_name : str
    pickled_cloner : bytearray
    event_context : EventContext
    orchestrator : str
    container_tag : Optional[str]
    schema: str = "v1"

@dataclass(frozen=True)
class DelegatedScanMessageBase(ScanHeader):
    details : DelegatedScanDetails
    details_signature : bytearray

@dataclass(frozen=True)
class DelegatedScanMessage(DelegatedScanMessageBase):
    capture_logs : bool
    schema: str = "v1"

@dataclass(frozen=True)
class DelegatedScanResultMessage(DelegatedScanMessageBase):
    resolver_results : bytearray
    container_results : bytearray
    exit_code: int
    logs : Optional[bytearray]
