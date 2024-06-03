from enum import Enum

class __base_enum(Enum):
    def __str__(self):
        return str(self.value)   

    def __repr__(self):
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



