import subprocess
import sys
import os
from .exceptions import GitError
from .repo_status import RepoStatus

class GitOperations:
    """
    Handles the execution of local Git commands.
    """

    def _run_command(self, command: list[str], cwd: str = ".", strip: bool = True):
        """
        A private helper to run git commands and handle errors.

        Args:
            command (list[str]): The command to execute.
            cwd (str): The working directory to run the command in.

        Raises:
            GitError: If the command fails.
        """
        try:
            # Resolve the path to an absolute path for consistency
            abs_cwd = os.path.abspath(cwd)         
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=abs_cwd
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise GitError(f"Git command failed: {command}\nError: {stderr.strip()}")
            if strip:
                return stdout.strip()
            else:
                return stdout

        except FileNotFoundError:
            raise GitError("`git` command not found. Is Git installed and in your PATH?")
        except Exception as e:
            raise GitError(f"An unexpected error occurred: {e}")

    def is_git_repo(self, path: str = ".") -> bool:
        """Checks if the given path is a Git repository."""
        abs_path = os.path.abspath(path)
        return os.path.isdir(os.path.join(abs_path, ".git"))

    def init(self, path: str = "."):
        """Initializes a new Git repository in the specified path."""
        self._run_command(["git", "init"], cwd=path)

    def add_remote(self, remote_url: str, path: str = "."):
        """Adds a new remote named 'origin'."""
        self._run_command(["git", "remote", "add", "origin", remote_url], cwd=path)

    def pull(self, branch_name: str, path: str = "."):
        """Pulls a branch from the 'origin' remote."""
        self._run_command(["git", "pull", "origin", branch_name], cwd=path)

    def create_branch(self, branch_name: str, start_point: str = "HEAD", path: str = "."):
        """Creates a new branch from a starting point."""
        self._run_command(["git", "branch", branch_name, start_point], cwd=path)

    def switch_branch(self, branch_name: str, path: str = "."):
        """Switches to an existing branch."""
        self._run_command(["git", "checkout", branch_name], cwd=path)

    def push_branch(self, branch_name: str, set_upstream: bool = False, path: str = "."):
        """Pushes a branch to the 'origin' remote."""
        cmd = ["git", "push", "origin", branch_name]
        if set_upstream:
            cmd.insert(2, "-u")
        self._run_command(cmd, cwd=path)

    def fetch(self, remote: str = "origin", path: str = "."):
        """Fetches updates from a remote repository."""
        self._run_command(["git", "fetch", remote], cwd=path)

    def clone(self, clone_url: str, repo_name: str, target_dir: str = ".") -> str:
        """
        Clones a repository into a specific target directory.
        'git clone' will create a new folder named after the repo inside the target_dir.
        """
        abs_target_dir = os.path.abspath(target_dir)
        final_repo_path = os.path.join(abs_target_dir, repo_name)

        if os.path.exists(final_repo_path):
            raise GitError(f"Destination path '{final_repo_path}' already exists.")

        try:
            os.makedirs(abs_target_dir, exist_ok=True)
        except OSError as e:
            raise GitError(f"Could not create target directory '{abs_target_dir}': {e}")

        self._run_command(["git", "clone", clone_url], cwd=abs_target_dir)
        return final_repo_path

    def add_submodule(self, repo_url: str, path: str, parent_path: str = "."):
        """Adds a new Git submodule."""
        self._run_command(["git", "submodule", "add", repo_url, path], cwd=parent_path)
        
    def add(self, files: list[str], path: str = "."):
        """Adds file contents to the index."""
        cmd = ["git", "add"] + files
        self._run_command(cmd, cwd=path)

    def commit(self, message: str, path: str = "."):
        """Records changes to the repository."""
        self._run_command(["git", "commit", "-m", message], cwd=path)
        
    def get_root(self, path: str = ".") -> str:
        """Finds the root directory of the git repository."""
        return self._run_command(["git", "rev-parse", "--show-toplevel"], cwd=path)

    def get_submodules(self, path: str = ".") -> list[str]:
        """Gets a list of submodule paths."""
        try:
            # This command lists submodules, e.g., " 1234abcd... path/to/submodule (HEAD)"
            status_output = self._run_command(["git", "submodule", "status"], cwd=path)
            if not status_output:
                return []
            # Extract just the path part
            return [line.strip().split()[1] for line in status_output.splitlines()]
        except GitError:
            # If the command fails (e.g., no submodules), return an empty list
            return []
        
    def get_current_branch(self, path: str = ".") -> str:
        """Gets the name of the current active branch."""
        return self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    
    def push_all(self, path: str = "."):
        """Pushes all branches to the remote."""
        self._run_command(["git", "push", "--all"], cwd=path)
        
        
    def get_status(self, path: str = ".") -> RepoStatus:
        """
        Gets the detailed status of the repository at the given path, including
        lists of files for each state.

        Args:
            path (str): The path to the repository.

        Returns:
            RepoStatus: An object containing the branch and lists of files.
        """
        branch = self.get_current_branch(path)
        status_output = self._run_command(["git", "status", "--porcelain"], cwd=path, strip=False)

        staged_files = []
        unstaged_files = []
        untracked_files = []

        if not status_output:
            return RepoStatus(branch=branch)

        for line in status_output.splitlines():
            code = line[:2]
            filename = line[3:]

            if code == '??':
                untracked_files.append(filename)
            else:
                # Staged changes (M, A, D, R, C in the first char)
                if code[0] != ' ':
                    staged_files.append(filename)
                # Unstaged/Modified changes (M, D in the second char)
                if code[1] != ' ':
                    unstaged_files.append(filename)
        
        return RepoStatus(
            branch=branch,
            staged=staged_files,
            unstaged=unstaged_files,
            untracked=untracked_files
        )
        
    def get_remote_url(self, remote_name: str = "origin", path: str = ".") -> str:
        """Gets the URL of a specified remote."""
        return self._run_command(["git", "config", "--get", f"remote.{remote_name}.url"], cwd=path)
    
    def delete_remote_branch(self, branch_name: str, remote_name: str = "origin", path: str = "."):
        """Deletes a branch from the specified remote."""
        self._run_command(["git", "push", remote_name, "--delete", branch_name], cwd=path)
        
    def delete_local_branch(self, branch_name: str, force: bool = False, path: str = "."):
        """Deletes a local branch."""
        cmd = ["git", "branch", "-d", branch_name]
        if force:
            cmd[2] = "-D"
        self._run_command(cmd, cwd=path)
        
    def get_latest_tag(self, path: str = ".") -> str | None:
        """
        Gets the latest version tag from the repository using semantic version sorting.
        Returns None if no tags are found.
        """
        try:
            # Sorts tags by version number (e.g., v1.10.0 comes after v1.9.0)
            # and returns the most recent one.
            return self._run_command(["git", "tag", "-l", "--sort=-v:refname"], cwd=path).splitlines()[0]
        except (GitError, IndexError):
            # Fails if no tags exist or command fails
            return None
        
    def create_tag(self, tag_name: str, message: str, path: str = "."):
        """Creates a new annotated tag."""
        self._run_command(["git", "tag", "-a", tag_name, "-m", message], cwd=path)

    def push_tags(self, path: str = "."):
        """Pushes all tags to the remote."""
        self._run_command(["git", "push", "--tags"], cwd=path)
        
    def get_all_branches(self, path: str = ".") -> list[str]:
        """Gets a list of all local and remote branches."""
        # Get local branches
        local_branches_output = self._run_command(["git", "branch"], cwd=path)
        local_branches = [b.replace("* ", "").strip() for b in local_branches_output.splitlines()]

        # Get remote branches
        remote_branches_output = self._run_command(["git", "branch", "-r"], cwd=path)
        remote_branches = [b.replace("origin/", "").strip() for b in remote_branches_output.splitlines() if '->' not in b]

        # Combine and remove duplicates
        all_branches = sorted(list(set(local_branches + remote_branches)))
        return all_branches
