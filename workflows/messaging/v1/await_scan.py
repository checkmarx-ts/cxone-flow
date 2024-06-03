from ..scan_message import ScanMessage
from dataclasses import dataclass
from ..util import is_expired


@dataclass(frozen=True)
class ScanAwaitMessage(ScanMessage):
    drop_by: str
    schema: str = "v1"

    def is_expired(self):
        return is_expired(self.drop_by)

