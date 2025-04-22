from dataclasses import dataclass, asdict, make_dataclass
from dataclasses_json import dataclass_json
from datetime import datetime, UTC
import uuid


@dataclass_json
@dataclass(frozen=True)
class BaseMessage:
    @classmethod
    def factory(clazz, **kwargs):
        return clazz(**kwargs)

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(clazz, json : dict):
        return make_dataclass(clazz.__name__, json)

    def to_binary(self):
        # pylint: disable=E1101
        return self.to_json().encode('UTF-8')
    
    @classmethod
    def from_binary(clazz, json_bin : bytearray):
        decoded = json_bin.decode()
        # pylint: disable=E1101
        return clazz.from_json(decoded)
    

@dataclass_json
@dataclass(frozen=True)
class StampedMessage(BaseMessage):
    timestamp : str
    correlation_id : str

    @classmethod
    def factory(clazz, correlation_id=uuid.uuid4(), **kwargs):
        return clazz(timestamp=datetime.now(UTC).isoformat(), correlation_id=correlation_id, **kwargs)
