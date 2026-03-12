from workflows.messaging.scan_message import ScanMessage
from dataclasses import dataclass
from workflows.messaging.util import is_expired


@dataclass(frozen=True)
class ScanAwaitMessage(ScanMessage):
    drop_by: str

    def is_expired(self):
        return is_expired(self.drop_by)

