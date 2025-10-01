from workflows.messaging.scan_message import ScanMessage
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ScanFeedbackMessage(ScanMessage):
  is_error : Optional[bool] = False
  error_msg : Optional[str] = "NA"
