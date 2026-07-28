class BitbucketCloudProjectNaming:

    @staticmethod
    def create_project_name(
        organization: str, project_key: str, project_name: str, repo_slug: str
    ) -> str:
        return f"{organization}/{project_key}/{project_name}/{repo_slug}"
