from pathlib import Path
from jsonpath_ng import parse
from workflows.messaging import PRDetails
from typing import Callable


class PullRequestDecoration:
    __cx_embed_header_img = "![CheckmarxOne](https://camo.githubusercontent.com/450121ab9d772ac3f1186c2dde5608322249cba9183cd43b34ac7a71e71584b9/68747470733a2f2f63646e2e6173742e636865636b6d6172782e6e65742f696e746567726174696f6e732f6c6f676f2f436865636b6d6172782e706e67)"

    __comment = "[//]:#"
    __header_begin = __comment + "begin:header"
    __header_end = __comment + "end:header"

    __annotation_begin = __comment + "begin:ann"
    __annotation_end = __comment + "end:ann"

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


    def __init__(self):
        self.__elements = {
            PullRequestDecoration.__header_begin : [],
            PullRequestDecoration.__header_end : None,
            PullRequestDecoration.__annotation_begin : [],
            PullRequestDecoration.__annotation_end : None,
            PullRequestDecoration.__details_begin : [],
            PullRequestDecoration.__details_end : None,
        }

    @staticmethod
    def scan_link(display_url : str, project_id : str, scanid : str):
        return f"[{scanid}]({display_url}{Path("projects") / Path(project_id) / Path(f"scans?id={scanid}&filter_by_Scan_Id={scanid}")})"

    @staticmethod
    def link(url : str, display_name : str):
        return f"[{display_name}]({url})"

    @staticmethod
    def severity_indicator(severity : str):
        return PullRequestDecoration.__severity_map[severity.lower()] \
            if severity.lower() in PullRequestDecoration.__severity_map.keys() else PullRequestDecoration.__default_emoji

    @staticmethod
    def description_link(display_url : str, project_id : str, scanid : str, name : str):
        pass

    @staticmethod
    def result_link(display_url : str, project_id : str, scanid : str, result_id : str):
        pass

    @staticmethod
    def source_file_link(blob_url : str, file_path : str, line : str):
        pass

    def add_to_annotation(self, line : str):
        self.__elements[PullRequestDecoration.__annotation_begin].append(line)

    def reset_annotation(self):
        self.__elements[PullRequestDecoration.__annotation_begin] = []

    def add_detail(self, severity : str, issue : str, source : str, link : str):
        self.__elements[PullRequestDecoration.__details_begin].append(f"| {severity} | {issue} | {source} | {link} |")

    def start_detail_section(self, title : str):
        self.__elements[PullRequestDecoration.__details_begin] = [f"# {title}", "\n", "| Severity | Issue | Source | Checkmarx Insight |", "| - | - | - | - |"]


    @property
    def content(self):
        content = []

        self.__elements[PullRequestDecoration.__header_begin] = [PullRequestDecoration.__cx_embed_header_img]

        for k in self.__elements.keys():
            content.append("\n")
            if self.__elements[k] is not None:
                for item in self.__elements[k]:
                    content.append(item)
        
        return "\n".join(content)



class PullRequestAnnotation(PullRequestDecoration):
    def __init__(self, display_url : str, project_id : str, scanid : str, annotation : str):
        super().__init__()
        self.add_to_annotation(f"{annotation}: {PullRequestDecoration.scan_link(display_url, project_id, scanid)}")

class PullRequestFeedback(PullRequestDecoration):
    __sast_results_query = parse("$.scanResults.resultsList[*]")
    __sca_results_query = parse("$.scaScanResults.packages[*]")
    __iac_results_query = parse("$.iacScanResults.technology[*]")
    __resolved_results_query = parse("$.resolvedVulnerabilities.resolvedVulnerabilities[*]")

    __scanner_stat_query = parse("$.scanInformation.scannerStatus[*]")

    def __init__(self, display_url : str,  project_id : str, scanid : str, enhanced_report : dict, code_permalink_func : Callable, pr_details : PRDetails):
        super().__init__()
        self.__enhanced_report = enhanced_report
        self.__permalink = code_permalink_func

        self.__add_annotation_section(display_url, project_id, scanid)

        self.add_sast_details(pr_details)

    def add_sast_details(self, pr_details):

        self.start_detail_section("SAST Results")
        for result in PullRequestFeedback.__sast_results_query.find(self.__enhanced_report):
            x = result.value
            describe_link = PullRequestDecoration.link(x['queryDescriptionLink'], x['queryName'])
            for vuln in x['vulnerabilities']:
                self.add_detail(PullRequestDecoration.severity_indicator(vuln['severity']), describe_link, 
                                PullRequestDecoration.link(self.__permalink(pr_details.organization, 
                                                                            pr_details.repo_project, pr_details.repo_slug, pr_details.source_branch, 
                                                                            vuln['sourceFileName'], vuln['sourceLine']), 
                                                           f"{vuln['sourceFileName']};{vuln['sourceLine']}"), 
                                PullRequestDecoration.link(vuln['resultViewerLink'], "Attack Vector"))

    def __add_annotation_section(self, display_url, project_id, scanid):
        self.add_to_annotation(f"**Results for Scan ID {PullRequestDecoration.scan_link(display_url, project_id, scanid)}**")
        self.add_to_annotation("# Scanners")
        for engine_status in PullRequestFeedback.__scanner_stat_query.find(self.__enhanced_report):
            x = engine_status.value
            self.add_to_annotation(f"* {x['name']} - *{x['status']}*")
