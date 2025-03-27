

class BitbucketProjectNaming:

  @staticmethod
  def create_project_name(project_key : str, project_name : str, repo_name : str) -> str:
    return f"{project_key}/{project_name}/{repo_name}"
