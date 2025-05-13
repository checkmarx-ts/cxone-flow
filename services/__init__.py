from dataclasses import dataclass
from re import Pattern
from cxone_service import CxOneService
from scm_services import SCMService
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService
from kickoff_services import KickoffService
from naming_services import ProjectNamingService

@dataclass(frozen=True)
class CxOneFlowServices:
    matcher : Pattern
    cxone : CxOneService
    scm : SCMService
    pr : PRFeedbackService
    resolver : ResolverScanService
    kickoff : KickoffService
    naming : ProjectNamingService


