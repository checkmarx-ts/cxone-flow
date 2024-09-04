from pathlib import Path
from jsonpath_ng import parse
from jsonpath_ng.ext import parser
from workflows.messaging import PRDetails
from typing import Callable, List, Type, Dict
from . import ResultSeverity, ResultStates
import re


class PullRequestDecoration:
    __cx_embed_header_img = "![CheckmarxOne](https://camo.githubusercontent.com/450121ab9d772ac3f1186c2dde5608322249cba9183cd43b34ac7a71e71584b9/68747470733a2f2f63646e2e6173742e636865636b6d6172782e6e65742f696e746567726174696f6e732f6c6f676f2f436865636b6d6172782e706e67)"

    __comment = "[//]:#"

    __identifier = __comment + "cxoneflow"

    __comment_match = re.compile(f"\\[//\\]:#cxoneflow")

    __header_begin = __comment + "begin:header"
    __header_end = __comment + "end:header"

    __annotation_begin = __comment + "begin:ann"
    __annotation_end = __comment + "end:ann"

    __summary_begin = __comment + "begin:summary"
    __summary_end = __comment + "end:summary"

    __details_begin = __comment + "begin:details"
    __details_end = __comment + "end:details"


    __severity_map = {
        "critical" : "CRITICAL",
        "high" : "HIGH",
        "medium" : "MEDIUM",
        "low" : "LOW",
        "information" : "INFO",
        "info" : "INFO",
        "informational" : "INFO"
    }

    @staticmethod
    def matches_identifier(text : str):
        return PullRequestDecoration.__comment_match.match(text.replace("\n", ""))


    def __init__(self):
        self.__elements = {
            PullRequestDecoration.__identifier : [PullRequestDecoration.__identifier],
            PullRequestDecoration.__header_begin : [PullRequestDecoration.__cx_embed_header_img],
            PullRequestDecoration.__header_end : None,
            PullRequestDecoration.__annotation_begin : [],
            PullRequestDecoration.__annotation_end : None,
            PullRequestDecoration.__summary_begin : [],
            PullRequestDecoration.__summary_end : None,
            PullRequestDecoration.__details_begin : [],
            PullRequestDecoration.__details_end : None,
        }

    @staticmethod
    def scan_link(display_url : str, project_id : str, scanid : str, branch : str):
        return f"[{scanid}]({display_url}{Path("projects") / Path(project_id) / Path(f"scans?id={scanid}&filter_by_Scan_Id={scanid}&branch={branch}")})"

    @staticmethod
    def sca_result_link(display_url : str, project_id : str, scanid : str, title : str, cve : str, package_id : str):
        display_path = Path("results") / Path(project_id) / Path(scanid) / Path(f"sca?internalPath=")
        internal_path = f"%2Fvulnerabilities%2F{cve}%253A{package_id}%2FvulnerabilityDetailsGql"
        return f"[{title}]({display_url}{display_path}{internal_path})"

    @staticmethod
    def link(url : str, display_name : str):
        return f"[{display_name}]({url})"

    @staticmethod
    def severity_indicator(severity : str):
        return PullRequestDecoration.__severity_map[severity.lower()] \
            if severity.lower() in PullRequestDecoration.__severity_map.keys() else PullRequestDecoration.__default_emoji

    def add_to_annotation(self, line : str):
        self.__elements[PullRequestDecoration.__annotation_begin].append(line)

    def add_sast_detail(self, severity : str, issue : str, source_permalink : str, link : str):
        self.__elements[PullRequestDecoration.__details_begin].append(f"| {severity} | {issue} | {source_permalink} | {link} |")

    def start_sast_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# SAST Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Issue | Source | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| - | - | - | - |")

    def add_sca_detail(self, severity : str, package_name : str, package_version : str, link : str):
        self.__elements[PullRequestDecoration.__details_begin].append(f"| {severity} | {package_name} | {package_version} | {link} |")

    def start_sca_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# SCA Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Package Name | Package Version | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| - | - | - | - |")

    def add_iac_detail(self, severity : str, technology : str, source_permalink : str, query : str, link : str):
        self.__elements[PullRequestDecoration.__details_begin].append(f"| {severity} | {technology} | {source_permalink} | {query} | {link} |")

    def start_iac_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# IAC Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Technology | Source | Query | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| - | - | - | - | - |")

    def add_resolved_detail(self, severity : str, name : str, link : str):
        self.__elements[PullRequestDecoration.__details_begin].append(f"| {severity} | {name} | {link} |")

    def start_resolved_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# Resolved Issues")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Name | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| - | - | - |")


    def start_summary_section(self, included_severities : List[ResultSeverity]):
        sev_header = " | ".join([x.value for x in included_severities])

        self.__elements[PullRequestDecoration.__summary_begin].append("\n")
        self.__elements[PullRequestDecoration.__summary_begin].append("# Summary of Vulnerabilities")
        self.__elements[PullRequestDecoration.__summary_begin].append("\n")
        self.__elements[PullRequestDecoration.__summary_begin].append(f"| Engine | {sev_header} |")
        self.__elements[PullRequestDecoration.__summary_begin].append(f"{"|--".join("" for x in included_severities)}|--|--|")
        

    def add_summary_entry(self, engine: str, counts_by_sev : Dict[ResultSeverity, str], included_severities : List[ResultSeverity]):
        sev_part = "|".join([ str(counts_by_sev[sev]) for sev in included_severities])
        self.__elements[PullRequestDecoration.__summary_begin].append(f"|{engine}|{sev_part}|")



    def __get_content(self, keys : List[str]) -> str:
        content = []

        for k in keys:
            content.append("\n")
            if self.__elements[k] is not None:
                for item in self.__elements[k]:
                    content.append(item)
        
        return "\n".join(content)

    @property
    def summary_content(self):
        return self.__get_content([x for x in self.__elements.keys() if x not in 
          [PullRequestDecoration.__details_begin, PullRequestDecoration.__details_end]])

    @property
    def full_content(self):
        return self.__get_content(self.__elements.keys())


class PullRequestAnnotation(PullRequestDecoration):
    def __init__(self, display_url : str, project_id : str, scanid : str, annotation : str, branch : str):
        super().__init__()
        self.add_to_annotation(f"{annotation}: {PullRequestDecoration.scan_link(display_url, project_id, scanid, branch)}")

class PullRequestFeedback(PullRequestDecoration):
    __sast_results_query = parse("$.scanResults.resultsList[*]")

    __sca_results_query = parse("$.scaScanResults.packages[*]")

    __iac_results_query = parse("$.iacScanResults.technology[*]")

    __resolved_results_query = parse("$.resolvedVulnerabilities")

    __scanner_stat_query = parse("$.scanInformation.scannerStatus[*]")

    @staticmethod
    def __test_in_enum(clazz : Type, value : str, exclusions : List[Type]):
        try:
            return clazz(value) in exclusions
        except ValueError:
            return False

    def __init__(self, excluded_severities : List[ResultSeverity], excluded_states : List[ResultStates], display_url : str,  
                 project_id : str, scanid : str, enhanced_report : dict, code_permalink_func : Callable, pr_details : PRDetails):
        super().__init__()
        self.__enhanced_report = enhanced_report
        self.__permalink = code_permalink_func
        self.__excluded_severities = excluded_severities
        self.__excluded_states = excluded_states

        self.__add_annotation_section(display_url, project_id, scanid, pr_details)
        self.__add_summary_section()
        self.__add_sast_details(pr_details)
        self.__add_sca_details(display_url, project_id, scanid)
        self.__add_iac_details(pr_details)
        self.__add_resolved_details()

    def __add_resolved_details(self):
        title_added = False
        for resolved in PullRequestFeedback.__resolved_results_query.find(self.__enhanced_report):
            for vuln in resolved.value['resolvedVulnerabilities']:

                for result in vuln['resolvedResults']:
                    if not PullRequestFeedback.__test_in_enum(ResultSeverity, result['severity'], self.__excluded_severities):

                        if not title_added:
                            self.start_resolved_detail_section()
                            title_added = True

                        self.add_resolved_detail(PullRequestDecoration.severity_indicator(result['severity']),
                                                vuln['vulnerabilityName'], 
                                                PullRequestDecoration.link(result['vulnerabilityLink'], "View"))

    def __add_iac_details(self, pr_details):
        title_added = False
        for result in PullRequestFeedback.__iac_results_query.find(self.__enhanced_report):
            x = result.value

            for query in x['queries']:
                for result in query['resultsList']:
                    if not (PullRequestFeedback.__test_in_enum(ResultStates, result['state'], self.__excluded_states) or 
                        PullRequestFeedback.__test_in_enum(ResultSeverity, result['severity'], self.__excluded_severities)):

                        if not title_added:
                            self.start_iac_detail_section()
                            title_added = True

                        self.add_iac_detail(PullRequestDecoration.severity_indicator(result['severity']), x['name'],
                                            f"`{result['fileName']}`{PullRequestDecoration.link(self.__permalink(pr_details.organization, 
                                        pr_details.repo_project, pr_details.repo_slug, pr_details.source_branch, 
                                        result['fileName'], 1), "view")}", query['queryName'], 
                                            PullRequestDecoration.link(result['resultViewerLink'], "Risk Details"))

    def __add_sca_details(self, display_url, project_id, scanid):
        title_added = False
        for result in PullRequestFeedback.__sca_results_query.find(self.__enhanced_report):
            x = result.value

            
            for category in x['packageCategory']:
                for cat_result in category['categoryResults']:
                    if not (PullRequestFeedback.__test_in_enum(ResultStates, cat_result['state'], self.__excluded_states) or 
                        PullRequestFeedback.__test_in_enum(ResultSeverity, cat_result['severity'], self.__excluded_severities)):

                        if not title_added:
                            self.start_sca_detail_section()
                            title_added = True

                        self.add_sca_detail(PullRequestDecoration.severity_indicator(cat_result['severity']),
                                            x['packageName'], x['packageVersion'], 
                                            PullRequestDecoration.sca_result_link(display_url, project_id, scanid, "Risk Details", 
                                                                                cat_result['cve'], x['packageId']))


    def __add_sast_details(self, pr_details):
        title_added = False
        for result in PullRequestFeedback.__sast_results_query.find(self.__enhanced_report):

            x = result.value
            describe_link = PullRequestDecoration.link(x['queryDescriptionLink'], x['queryName'])
            for vuln in x['vulnerabilities']:
                if not (PullRequestFeedback.__test_in_enum(ResultStates, vuln['state'], self.__excluded_states) or 
                        PullRequestFeedback.__test_in_enum(ResultSeverity, vuln['severity'], self.__excluded_severities)):

                    if not title_added:
                        self.start_sast_detail_section()
                        title_added = True

                    self.add_sast_detail(PullRequestDecoration.severity_indicator(vuln['severity']), describe_link, 
                                    f"`{vuln['sourceFileName']}`;{PullRequestDecoration.link(self.__permalink(pr_details.organization, 
                                        pr_details.repo_project, pr_details.repo_slug, pr_details.source_branch, 
                                        vuln['sourceFileName'], vuln['sourceLine']), 
                                        vuln['sourceLine'])}", 
                                        PullRequestDecoration.link(vuln['resultViewerLink'], "Attack Vector"))

    @staticmethod
    def __translate_engine_status(status_string : str) -> str:
        match status_string:
            case "Completed":
                return "&#x2705;"

            case _:
                return "&#x274c;"

    def __add_annotation_section(self, display_url : str, project_id : str, scanid : str, pr_details : PRDetails):
        self.add_to_annotation(f"**Results for Scan ID {PullRequestDecoration.scan_link(display_url, project_id, scanid, pr_details.source_branch)}**")

        status_content = ""
        for engine_status in PullRequestFeedback.__scanner_stat_query.find(self.__enhanced_report):
            stat = f"{PullRequestFeedback.__translate_engine_status(engine_status.value['status'])}&nbsp;**{engine_status.value['name']}**"
            status_content = f"{status_content}{stat}&nbsp;&nbsp;"

        self.add_to_annotation(f"\n{status_content}")
    
    @staticmethod
    def __init_result_count_map() -> Dict[ResultSeverity, str]:
        return {k:"N/R" for k in ResultSeverity}

    def __add_engine_summary(self, engine : str, severitiesBreakdown : List[Dict[str, any]], included_severities : List[ResultSeverity]):
        counts = PullRequestFeedback.__init_result_count_map()

        for entry in severitiesBreakdown:
            counts[ResultSeverity(entry.value['level'])] = str(entry.value['value'])

        self.add_summary_entry(engine, counts, included_severities)


    def __get_result_count_map(self, query_gen : Callable[[str], str]) -> Dict[ResultSeverity, str]:
        counts = PullRequestFeedback.__init_result_count_map()
        sev_incl = PullRequestFeedback.__included_severities(self.__excluded_severities)

        for sev in sev_incl:
            for sev_value in sev.values:
                query = parser.parse(query_gen(sev_value))
                found = query.find(self.__enhanced_report)
                if len(found) > 0:
                    counts[sev] = str(len(found))
                    break
        
        return counts

    def __add_sast_summary(self):
        sev_incl = PullRequestFeedback.__included_severities(self.__excluded_severities)

        self.add_summary_entry("SAST", 
          self.__get_result_count_map(
              lambda sev_value:  f"$.scanResults.resultsList[*].vulnerabilities[?(@.state!='Not Exploitable' & @.severity=='{sev_value}')]"), sev_incl)

    def __add_sca_summary(self):
        sev_incl = PullRequestFeedback.__included_severities(self.__excluded_severities)

        self.add_summary_entry("SCA", 
          self.__get_result_count_map(
              lambda sev_value:  f"$.scaScanResults.packages[*].packageCategory[*].categoryResults[?(@.state!='Not Exploitable' & @.severity=='{sev_value}')]"),
              sev_incl)

    def __add_iac_summary(self):
        sev_incl = PullRequestFeedback.__included_severities(self.__excluded_severities)

        self.add_summary_entry("IaC", 
          self.__get_result_count_map(
              lambda sev_value:  f"$.iacScanResults.technology[*].queries[*].resultsList[?(@.state!='Not Exploitable' & @.severity=='{sev_value}')]"),
              sev_incl)
        
    @staticmethod
    def __included_severities(excluded_severities : List[ResultSeverity]) -> List[ResultSeverity]:
        return [x for x in ResultSeverity if x not in excluded_severities]

    def __add_summary_section(self):

        self.start_summary_section(PullRequestFeedback.__included_severities(self.__excluded_severities))
        self.__add_sast_summary()
        self.__add_sca_summary()
        self.__add_iac_summary()
