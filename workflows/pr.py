from pathlib import Path

class PullRequestDecoration:
    __cx_embed_header_img = "![CheckmarxOne](https://camo.githubusercontent.com/450121ab9d772ac3f1186c2dde5608322249cba9183cd43b34ac7a71e71584b9/68747470733a2f2f63646e2e6173742e636865636b6d6172782e6e65742f696e746567726174696f6e732f6c6f676f2f436865636b6d6172782e706e67)"

    __comment = "[//]:#"
    __header_begin = __comment + "begin:header"
    __header_end = __comment + "end:header"

    __annotation_begin = __comment + "begin:ann"
    __annotation_end = __comment + "end:ann"

    __body_begin = __comment + "begin:body"
    __body_end = __comment + "end:body"

    @staticmethod
    def from_markdown(markdown : str):
        inst = PullRequestDecoration()
        lines = markdown.split("\n")

        current_list = None

        for line in lines:
            if line.startswith(PullRequestDecoration.__comment):
                current_list = inst.__elements[line]
                continue

            if current_list is not None:
                current_list.append(line)

        return inst

    def __init__(self):
        self.__elements = {
            PullRequestDecoration.__header_begin : [],
            PullRequestDecoration.__header_end : None,
            PullRequestDecoration.__annotation_begin : [],
            PullRequestDecoration.__annotation_end : None,
            PullRequestDecoration.__body_begin : [],
            PullRequestDecoration.__body_end : None,
        }

    @staticmethod
    def scan_link(display_url : str, project_id : str, scanid : str):
        return f"[{scanid}]({display_url}{Path("projects") / Path(project_id) / Path(f"scans?id={scanid}&filter_by_Scan_Id={scanid}")})"

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


    @property
    def content(self):
        
        self.__elements[PullRequestDecoration.__header_begin] = [PullRequestDecoration.__cx_embed_header_img]

        return "\n".join([PullRequestDecoration.__header_begin] + self.__elements[PullRequestDecoration.__header_begin] + [PullRequestDecoration.__header_end]
                         + [PullRequestDecoration.__annotation_begin] + self.__elements[PullRequestDecoration.__annotation_begin] + [PullRequestDecoration.__annotation_end]
                         + [PullRequestDecoration.__body_begin] + self.__elements[PullRequestDecoration.__body_begin] + [PullRequestDecoration.__body_end]
                         )



class PullRequestAnnotation(PullRequestDecoration):
    def __init__(self, display_url : str, project_id : str, scanid : str, annotation : str):
        super().__init__()
        self.add_to_annotation(f"{annotation}: {PullRequestDecoration.scan_link(display_url, project_id, scanid)}")

