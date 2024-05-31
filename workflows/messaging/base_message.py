from dataclasses import dataclass
from datetime import datetime
from dataclasses_json import dataclass_json
from .util import is_expired

@dataclass_json
@dataclass(frozen=True)
class BaseMessage:
    moniker: str
    drop_by: str

    def to_binary(self):
        return self.to_json().encode('UTF-8')
    
    @classmethod
    def from_binary(clazz, json_bin : bytearray):
        decoded = json_bin.decode()
        return clazz.from_json(decoded)
    
    def is_expired(self):
        return is_expired(self.drop_by)
