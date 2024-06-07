from enum import Enum
from aenum import MultiValueEnum

class __base_enum(Enum):
    def __str__(self):
        return str(self.value)   


class ScanWorkflow(__base_enum):
    PR = "pr"
    PUSH = "push"

class FeedbackWorkflow(__base_enum):
    PR = "pr"

class ScanStates(__base_enum):
    AWAIT = "await"
    FEEDBACK = "feedback"
    ANNOTATE = "annotate"


class GoofyEnum(MultiValueEnum):
    def __repr__(self):
        return str(self.value)

    @classmethod
    def names(clazz):
        return list(clazz._member_map_.values())

class ResultStates(GoofyEnum):
    TO_VERIFY = "To Verify"
    NOT_EXPLOITABLE = "Not Exploitable"
    PROP_NOT_EXPLOITABLE = "Proposed Not Exploitable"
    CONFIRMED = "Confirmed"
    URGENT = "Urgent"


class ResultSeverity(GoofyEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info", "Information"




