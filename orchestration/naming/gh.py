

class GithubProjectNaming:

  @staticmethod
  def create_project_name(organization : str, repo_name : str) -> str:
    return f"{organization}/{repo_name}"
