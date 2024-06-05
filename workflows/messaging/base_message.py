from dataclasses import dataclass, asdict, make_dataclass, field
from dataclasses_json import dataclass_json
from datetime import datetime, UTC

@dataclass_json
@dataclass(frozen=True)
class BaseMessage:
    timestamp : str = field(default=datetime.now(UTC).isoformat(), init=False)

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(clazz, json : dict):
        return make_dataclass(clazz.__name__, json)

    def to_binary(self):
        return self.to_json().encode('UTF-8')
    
    @classmethod
    def from_binary(clazz, json_bin : bytearray):
        decoded = json_bin.decode()
        return clazz.from_json(decoded)
    

