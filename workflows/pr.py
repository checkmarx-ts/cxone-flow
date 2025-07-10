from pathlib import Path
from jsonpath_ng import parse
from jsonpath_ng.ext import parser
from workflows.messaging import PRDetails
from typing import Callable, List, Type, Dict
from . import ResultSeverity, ResultStates
from sortedcontainers import SortedList
import re, urllib


class SortedDetailRows:
    class DetailRow:
        def __init__(self, severity : ResultSeverity, output_order : List[str], **kwargs):
            self.__severity = severity
            self.__output_order = output_order
            self.__field_data = kwargs

        @property
        def severity(self) -> ResultSeverity:
            return self.__severity

        @property
        def severity_rank_key(self) -> str:
            return f"{self.__severity.rank:03}"
        
        def __getitem__(self, key) -> str:
            return self.__field_data.get(key, "")
        
        def __str__(self):
            return f"| {' | '.join([self.__field_data[field] for field in self.__output_order])} |"
        
    def __init__(self, header_order : List[str], key_lambda : Callable[[DetailRow], str]):
        self.__details = SortedList(key = key_lambda)
        self.__header_order = header_order

    def add_row(self, severity : ResultSeverity, **kwargs):
        self.__details.add(SortedDetailRows.DetailRow(severity, self.__header_order, **kwargs))

    def __str__(self):
        return "\n".join([str(x) for x in self.__details])


class PullRequestDecoration:

    class SastDetailRows(SortedDetailRows):
        def __init__(self):
            super().__init__(["severity_image_link","issue", "source_permalink", "viewer_link"], lambda x: x.severity_rank_key + x['issue'])

    class ScaDetailRows(SortedDetailRows):

        @staticmethod
        def normalized_version(version : str) -> str:
            try:
                elements = version.split('.')
                
                if len(elements) == 0:
                    return version
                
                padded_elements = [f"{int(x):03}" for x in elements]
                return ".".join(padded_elements)
            except ValueError:
                return version

        def __init__(self):
            super().__init__(["severity_image_link","cve", "package", "viewer_link"], 
                             lambda x: x.severity_rank_key + x['package_name'] + x['package_version'] + x['cve'])


    class IacDetailRows(SortedDetailRows):
        def __init__(self):
            super().__init__(["severity_image_link", "technology", "source_permalink", "query", "viewer_link"], lambda x: x.severity_rank_key + x['technology'])

    class ResolvedDetailRows(SortedDetailRows):
        def __init__(self):
            super().__init__(["severity_image_link", "name", "viewer_link"], lambda x: x.severity_rank_key + x['name'])

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


    __default_severity = "info.png"

    __severity_map = {
        "critical" : "critical.png",
        "high" : "high.png",
        "medium" : "medium.png",
        "low" : "low.png",
        "information" : "info.png",
        "info" : "info.png",
        "informational" : "info.png"
    }

    @staticmethod
    def matches_identifier(text : str):
        return PullRequestDecoration.__comment_match.match(text.replace("\n", ""))
    

    def __init__(self, server_base_url : str):
        self.__server_base_url = server_base_url

        self.__elements = {
            PullRequestDecoration.__identifier : [PullRequestDecoration.__identifier],
            PullRequestDecoration.__header_begin : [PullRequestDecoration.header_image(self.__server_base_url)],
            PullRequestDecoration.__header_end : None,
            PullRequestDecoration.__annotation_begin : [],
            PullRequestDecoration.__annotation_end : None,
            PullRequestDecoration.__summary_begin : [],
            PullRequestDecoration.__summary_end : None,
            PullRequestDecoration.__details_begin : [],
            PullRequestDecoration.__details_end : None,
        }

        self.__sast_detail_rows = PullRequestDecoration.SastDetailRows()
        self.__sca_detail_rows = PullRequestDecoration.ScaDetailRows()
        self.__iac_detail_rows = PullRequestDecoration.IacDetailRows()
        self.__resolved_detail_rows = PullRequestDecoration.ResolvedDetailRows()

    @property
    def server_base_url(self) -> str:
        return self.__server_base_url
    

    @staticmethod
    def scan_link(display_url : str, project_id : str, scanid : str, branch : str):
        return f"[{scanid}]({display_url}{Path("projects") / 
                                          Path(project_id) / 
                                          Path(f"scans?id={scanid}&filter_by_Scan_Id={scanid}&branch={urllib.parse.quote_plus(branch)}")})"

    @staticmethod
    def sca_result_link(display_url : str, project_id : str, scanid : str, title : str, cve : str, package_id : str):
        display_path = Path("results") / Path(project_id) / Path(scanid) / Path(f"sca?internalPath=")
        internal_path = f"%2Fvulnerabilities%2F{cve}%253A{package_id}%2FvulnerabilityDetailsGql"
        return f"[{title}]({display_url}{display_path}{internal_path})"

    @staticmethod
    def link(url : str, display_name : str):
        return f"[{display_name}]({url})"

    @staticmethod
    def image(url : str, display_name : str):
        return f"![{display_name}]({url})"

    @staticmethod
    def header_image(server_base_url : str):
         return PullRequestDecoration.image(PullRequestDecoration._form_artifact_url(server_base_url, "checkmarx.png"), "CheckmarxOne")

    @staticmethod
    def _form_artifact_url(server_base_url : str, artifact_path : str) -> str:
        return f"{server_base_url.rstrip("/")}/artifacts/{urllib.parse.quote(artifact_path.lstrip("/"))}"

    @staticmethod
    def severity_indicator(server_base_url : str, severity : str):
        img = PullRequestDecoration.__severity_map[severity.lower()] \
            if severity.lower() in PullRequestDecoration.__severity_map.keys() else PullRequestDecoration.__default_severity
        return PullRequestDecoration.image(PullRequestDecoration._form_artifact_url(server_base_url, img), severity)

    def add_to_annotation(self, line : str):
        self.__elements[PullRequestDecoration.__annotation_begin].append(line)

    def add_sast_detail(self, severity : ResultSeverity, severity_image_link : str, issue : str, source_permalink : str, viewer_link : str):
        self.__sast_detail_rows.add_row(ResultSeverity(severity), 
                                        severity_image_link=severity_image_link,
                                        issue=issue,
                                        source_permalink=source_permalink,
                                        viewer_link=viewer_link)

    def start_sast_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# SAST Results")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Issue | Source | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| :-: | - | - | - |")
        self.__elements[PullRequestDecoration.__details_begin].append(self.__sast_detail_rows)

    def add_sca_detail(self, severity : ResultSeverity, severity_image_link : str, cve : str, package_name : str, package_version : str, viewer_link : str):
        self.__sca_detail_rows.add_row(ResultSeverity(severity), 
                                        severity_image_link=severity_image_link,
                                        cve=cve,
                                        package=f"{package_name}:{package_version}",
                                        viewer_link=viewer_link,
                                        package_name=package_name,
                                        package_version=PullRequestDecoration.ScaDetailRows.normalized_version(package_version))

    def start_sca_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# SCA Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | CVE | Package | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| :-: | - | - | - |")
        self.__elements[PullRequestDecoration.__details_begin].append(self.__sca_detail_rows)

    def add_iac_detail(self, severity : ResultSeverity, severity_image_link : str, technology : str, source_permalink : str, query : str, viewer_link : str):
        self.__iac_detail_rows.add_row(ResultSeverity(severity), 
                                        severity_image_link=severity_image_link,
                                        technology=technology,
                                        source_permalink=source_permalink,
                                        query=query,
                                        viewer_link=viewer_link)

    def start_iac_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# IAC Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Technology | Source | Query | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| :-: | - | - | - | - |")
        self.__elements[PullRequestDecoration.__details_begin].append(self.__iac_detail_rows)

    def add_resolved_detail(self, severity : ResultSeverity, severity_image_link : str, name : str, viewer_link : str):
        self.__resolved_detail_rows.add_row(ResultSeverity(severity), 
                                        severity_image_link=severity_image_link,
                                        name=name,
                                        viewer_link=viewer_link)

    def start_resolved_detail_section(self):
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("# Resolved SAST Results")
        self.__elements[PullRequestDecoration.__details_begin].append("\n")
        self.__elements[PullRequestDecoration.__details_begin].append("| Severity | Name | Checkmarx Insight |")
        self.__elements[PullRequestDecoration.__details_begin].append("| :-: | - | - |")
        self.__elements[PullRequestDecoration.__details_begin].append(self.__resolved_detail_rows)


    def start_summary_section(self, included_severities : List[ResultSeverity]):
        sev_header = " | ".join([x.value for x in included_severities])

        self.__elements[PullRequestDecoration.__summary_begin].append("\n")
        self.__elements[PullRequestDecoration.__summary_begin].append("# Summary of Vulnerabilities")
        self.__elements[PullRequestDecoration.__summary_begin].append("\n")
        self.__elements[PullRequestDecoration.__summary_begin].append(f"| Engine | {sev_header} |")
        self.__elements[PullRequestDecoration.__summary_begin].append(f"|--{"| :-: " * len(included_severities)}|")
        

    def add_summary_entry(self, engine: str, counts_by_sev : Dict[ResultSeverity, str], included_severities : List[ResultSeverity]):
        sev_part = "|".join([ str(counts_by_sev[sev]) for sev in included_severities])
        self.__elements[PullRequestDecoration.__summary_begin].append(f"|{engine}|{sev_part}|")



    def __get_content(self, keys : List[str]) -> str:
        content = []

        for k in keys:
            content.append("\n")
            if self.__elements[k] is not None:
                for item in self.__elements[k]:
                    content.append(str(item))
        
        return "\n".join(content)

    @property
    def summary_content(self):
        return self.__get_content([x for x in self.__elements.keys() if x not in 
          [PullRequestDecoration.__details_begin, PullRequestDecoration.__details_end]])

    @property
    def full_content(self):
        return self.__get_content(self.__elements.keys())


class PullRequestAnnotation(PullRequestDecoration):
    def __init__(self, display_url : str, project_id : str, scanid : str, annotation : str, branch : str, server_base_url : str):
        super().__init__(server_base_url)
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
                 project_id : str, scanid : str, enhanced_report : dict, code_permalink_func : Callable, pr_details : PRDetails,
                 server_base_url : str):
        super().__init__(server_base_url)
        self.__enhanced_report = enhanced_report
        self.__permalink = code_permalink_func
        self.__excluded_severities = excluded_severities
        self.__excluded_states = excluded_states

        self.__add_annotation_section(display_url, project_id, scanid, pr_details)
        self.__add_summary_section()
        self.__add_sast_details(pr_details)
        self.__add_resolved_details(project_id)
        self.__add_sca_details(display_url, project_id, scanid)
        self.__add_iac_details(pr_details)

    def __add_resolved_details(self, project_id : str):
        title_added = False
        for resolved in PullRequestFeedback.__resolved_results_query.find(self.__enhanced_report):
            for vuln in resolved.value['resolvedVulnerabilities']:

                for result in vuln['resolvedResults']:
                    if not PullRequestFeedback.__test_in_enum(ResultSeverity, result['severity'], self.__excluded_severities):

                        if not title_added:
                            self.start_resolved_detail_section()
                            title_added = True

                        # vulnerabilityLink has the scanid and projectid in the wrong order, so it needs to be fixed.
                        # It links to the previous scanid, so the URL needs to be parsed out and have the path fixed.

                        # Don't change the link if the link has been fixed in the report.
                        fixed_link = result['vulnerabilityLink']

                        parsed_url =  urllib.parse.urlparse(result['vulnerabilityLink'])
                        path_components = parsed_url.path.split("/")
                        if path_components[-1:].pop() == project_id:
                            path_components.pop()
                            path_components.insert(len(path_components) - 1, project_id)
                            fixed_link = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, "/".join(path_components), 
                                                                  parsed_url.params, parsed_url.query, parsed_url.fragment))

                        

                        self.add_resolved_detail(ResultSeverity(result['severity']), 
                                                PullRequestDecoration.severity_indicator(self.server_base_url, result['severity']),
                                                vuln['vulnerabilityName'], 
                                                PullRequestDecoration.link(fixed_link, "View"))

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

                        self.add_iac_detail(ResultSeverity(result['severity']), PullRequestDecoration.severity_indicator(self.server_base_url, result['severity']), 
                                            x['name'], f"`{result['fileName']}`{PullRequestDecoration.link(self.__permalink(pr_details.organization, 
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

                        self.add_sca_detail(ResultSeverity(cat_result['severity']), PullRequestDecoration.severity_indicator(self.server_base_url, cat_result['severity']),
                                            cat_result['cve'], x['packageName'], x['packageVersion'], 
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

                    self.add_sast_detail(ResultSeverity(vuln['severity']), 
                                    PullRequestDecoration.severity_indicator(self.server_base_url, vuln['severity']), describe_link, 
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
        # pylint: disable=E1133
        return {k:"-" for k in ResultSeverity}

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
        # pylint: disable=E1133
        return [x for x in ResultSeverity if x not in excluded_severities]

    def __add_summary_section(self):

        self.start_summary_section(PullRequestFeedback.__included_severities(self.__excluded_severities))
        self.__add_sast_summary()
        self.__add_sca_summary()
        self.__add_iac_summary()
