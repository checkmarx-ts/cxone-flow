from ..scan_message import ScanHeader
from ..base_message import BaseMessage
from dataclasses import dataclass
from api_utils.auth_factories import EventContext
from typing import Optional
from _version import __version__

@dataclass(frozen=True)
class DelegatedScanDetails(BaseMessage):
    clone_url : str
    commit_hash : str
    scan_branch : str
    scan_tags : dict
    file_filters : str
    project_id : str
    pickled_scm_service : bytearray
    pickled_cxone_service : bytearray
    event_context : EventContext
    orchestrator : str
    cxoneflow_version : str = __version__

@dataclass(frozen=True)
class DelegatedScanMessageBase(ScanHeader):
    details : DelegatedScanDetails
    details_signature : bytearray

@dataclass(frozen=True)
class DelegatedScanMessage(DelegatedScanMessageBase):
    capture_logs : bool

@dataclass(frozen=True)
class DelegatedScanResultMessage(DelegatedScanMessageBase):
    resolver_exit_code : Optional[int] = None
    scan_id : Optional[str] = None
    logs : Optional[bytearray] = None
