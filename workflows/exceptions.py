
class WorkflowException(BaseException):
    @staticmethod
    def unknown_resolver_tag(tag : str, clone_url : str):
        return WorkflowException(f"Unknown resolver tag [{tag}] when trying to orchestrate a resolver scan for [{clone_url}].")

    @staticmethod
    def invalid_tag(tag : str):
        return WorkflowException(f"Tag [{tag}] is not valid.  Only alphanumeric characters, dashes, and underscores are allowed.")
