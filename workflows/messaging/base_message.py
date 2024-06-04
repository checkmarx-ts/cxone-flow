from dataclasses import dataclass, asdict
from datetime import datetime
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass(frozen=True)
class BaseMessage:

    def as_dict(self):
        return asdict(self)


    def to_binary(self):
        return self.to_json().encode('UTF-8')
    
    @classmethod
    def from_binary(clazz, json_bin : bytearray):
        decoded = json_bin.decode()
        return clazz.from_json(decoded)
    

