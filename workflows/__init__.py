from enum import Enum
from aenum import MultiValueEnum, AutoNumberEnum

class __base_enum(Enum):
    def __str__(self):
        return str(self.value)   


class ScanWorkflow(__base_enum):
    PR = "pull-request"
    PUSH = "push"
class FeedbackWorkflow(__base_enum):
    PR = "pull-request"

class ScanStates(__base_enum):
    AWAIT = "await"
    FEEDBACK = "feedback"
    ANNOTATE = "annotate"
    EXECUTE = "exec"
    DONE = "finished"
    FAILURE = "failed"

class ExecTypes(__base_enum):
    RESOLVER = "sca-resolver"

class ResolverOps(__base_enum):
    SCAN = "run-scan"
    SCAN_COMPLETE = "scan-complete"

class GoofyEnum(MultiValueEnum):
    def __repr__(self):
        # pylint: disable=E1101
        return str(self.value)

    @classmethod
    def names(clazz):
        # pylint: disable=E1101
        return list(clazz._member_map_.values())

class ResultStates(GoofyEnum):
    TO_VERIFY = "To Verify"
    NOT_EXPLOITABLE = "Not Exploitable"
    PROP_NOT_EXPLOITABLE = "Proposed Not Exploitable"
    CONFIRMED = "Confirmed"
    URGENT = "Urgent"


class ResultSeverity(GoofyEnum):
    CRITICAL = "Critical", 0
    HIGH = "High", 1
    MEDIUM = "Medium", 2
    LOW = "Low", 3
    INFO = "Info", "Information", "", 4

    @property
    def rank(self):
        return self.values[-1:][0] # pylint: disable=E1101




