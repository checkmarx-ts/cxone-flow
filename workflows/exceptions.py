
class WorkflowException(BaseException):
    @staticmethod
    def unknown_resolver_tag(tag : str, clone_url : str):
        return WorkflowException(f"Unknown resolver tag [{tag}] when trying to orchestrate a resolver scan for [{clone_url}].")

    @staticmethod
    def invalid_tag(tag : str):
        return WorkflowException(f"Tag [{tag}] is not valid.  Only alphanumeric characters, dashes, and underscores are allowed.")

    @staticmethod
    def missing_report(project_id : str, scan_id : str):
        return WorkflowException(f"Project {project_id}: Report for scan {scan_id} not found.")
