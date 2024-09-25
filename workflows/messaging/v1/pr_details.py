from ..base_message import BaseMessage
from dataclasses import dataclass
from api_utils.auth_factories import EventContext

@dataclass(frozen=True)
class PRDetails(BaseMessage):
    clone_url: str
    repo_project : str
    repo_slug : str
    pr_id : str
    organization : str
    source_branch : str
    target_branch : str
    event_context : EventContext
    schema : str = "v1"
