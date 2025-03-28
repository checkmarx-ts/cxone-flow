

class AzureDevOpsProjectNaming:

  @staticmethod
  def create_project_name(collection_name : str, project_name : str, repo_name : str) -> str:
    return f"{collection_name}/{project_name}/{repo_name}"
