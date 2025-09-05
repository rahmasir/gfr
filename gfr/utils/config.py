# gfr/utils/config.py
import yaml
import os
from .git.operations import GitOperations, GitError

# const values
LAST_USED_MICROSERVICE = "last_used_microservice"
ORGANIZATION = "organization"

class GFRConfig:
    """
    Manages the .gfr.yml configuration file at the root of the project.
    """
    def __init__(self):
        try:
            git_ops = GitOperations()
            self.root_path = git_ops.get_root()
            self.config_path = os.path.join(self.root_path, ".gfr.yml")
            self.config = self._read_config()
        except GitError:
            # Handle case where we are not in a git repo
            self.root_path = None
            self.config_path = None
            self.config = {}

    def _read_config(self) -> dict:
        """Reads the YAML configuration file."""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _write_config(self):
        """Writes the current configuration to the YAML file."""
        if self.config_path:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.config, f)

    def get_last_used_microservice(self) -> str | None:
        """Retrieves the name of the last used microservice."""
        return self.config.get(LAST_USED_MICROSERVICE)

    def set_last_used_microservice(self, name: str):
        """Updates the name of the last used microservice."""
        self.config[LAST_USED_MICROSERVICE] = name
        self._write_config()
        
    def set_organization(self, organization: str):
        """update the organiztion we used for create and updating repository"""
        self.config[ORGANIZATION] = organization
        with open(os.path.join(os.getcwd(), '.gfr.yml'), 'w') as f:
            yaml.safe_dump(self.config, f)
        
    def get_organization(self) -> str | None:
        """retrieves the name of the organiztion we use in this repo"""
        return self.config.get(ORGANIZATION)