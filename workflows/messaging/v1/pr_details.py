from ..base_message import BaseMessage
from dataclasses import dataclass
from api_utils.auth_factories import EventContext


@dataclass(frozen=True)
class PushDetails(BaseMessage):
    clone_url: str
    repo_project : str
    repo_slug : str
    organization : str
    source_branch : str
    event_context : EventContext

@dataclass(frozen=True)
class PRDetails(PushDetails):
    pr_id : str
    target_branch : str
