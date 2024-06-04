from ..base_message import BaseMessage
from dataclasses import dataclass

@dataclass(frozen=True)
class PRDetails(BaseMessage):
    clone_url: str
    repo_project : str
    repo_slug : str
    pr_id : str
    organization : str
    schema : str = "v1"
