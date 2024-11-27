from dataclasses import dataclass
from re import Pattern
from cxone_service import CxOneService
from scm_services import SCMService
from workflows.pr_feedback_service import PRFeedbackService
from workflows.resolver_scan_service import ResolverScanService

@dataclass
class CxOneFlowServices:
    matcher : Pattern
    cxone : CxOneService
    scm : SCMService
    pr : PRFeedbackService
    resolver : ResolverScanService


