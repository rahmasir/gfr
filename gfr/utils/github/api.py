import os
from dotenv import load_dotenv
from github import Github, GithubException

# Import the manager and the custom exception
from .repositories import RepositoryManager, GitHubError
from .pull_requests import PullRequestManager
from .issues import IssueManager
from ..config import GFRConfig

class GitHubAPI:
    """A wrapper for the PyGithub library to handle auth and operations."""
    def __init__(self, organization: str = None):
        config = GFRConfig()
        organization_in_config_file = config.get_organization()
        # print(f"we are in github api init: org in config file is: {organization_in_config_file}")
        
        """Initializes the GitHub API client and its managers."""
        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")
        if organization:
            self.org_name = organization
        elif organization_in_config_file:
            self.org_name = organization_in_config_file
        else:
            self.org_name = os.getenv("GITHUB_ORGANIZATION")
        self.username = os.getenv("GITHUB_USERNAME")

        if not all([token, self.org_name, self.username]):
            raise GitHubError("Missing credentials in your .env file.")

        try:
            self._gh = Github(token)
            self._org = self._gh.get_organization(self.org_name)
            self._user = self._gh.get_user(self.username)
        except GithubException as e:
            error_message = f"Authentication or organization lookup failed. Details: {e.data.get('message', 'Unknown error')}"
            error_tip = "\nPlease check your network connection and ensure your GITHUB_TOKEN is correct and has the required permissions."
            raise GitHubError(error_message + error_tip)

        # --- Initialize and expose managers ---
        self.repos = RepositoryManager(self._gh, self._org)
        self.issues = IssueManager(self._gh, self._user)
        self.prs = PullRequestManager(self._gh, self._user)