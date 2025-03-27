
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import List, Optional


@dataclass_json
@dataclass(frozen=True)
class KickoffMsg:
    clone_urls : List[str]
    branch_name : str
    sha : str

    def __repr__(self):
        return f"{self.clone_urls}:{self.branch_name}@{self.sha}"

@dataclass_json
@dataclass(frozen=True)
class GithubKickoffMsg(KickoffMsg):
    repo_organization_name : str
    repo_name : str
    install_id : Optional[int] = None
    app_id : Optional[int] = None

@dataclass_json
@dataclass(frozen=True)
class AdoKickoffMsg(KickoffMsg):
    collection_name : str
    project_name : str
    repo_name : str

@dataclass_json
@dataclass(frozen=True)
class GitlabKickoffMsg(KickoffMsg):
    repo_path_with_namespace : str

@dataclass_json
@dataclass(frozen=True)
class BitbucketKickoffMsg(KickoffMsg):
    repo_name : str
    project_key : str
    project_name : str


@dataclass_json
@dataclass(frozen=True)
class ExecutingScan:
    project_name : str
    project_id : str
    scan_id : str
    scan_branch : str

    def __repr__(self):
        return f"{self.project_name}[{self.project_id}]:[{self.scan_id}]:[{self.scan_branch}]"

@dataclass_json
@dataclass(frozen=True)
class KickoffResponseMsg:
    running_scans : List[ExecutingScan]
    started_scan : Optional[ExecutingScan] = None



