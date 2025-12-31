# gfr - Git Flow Assistant of Rahmasir
#### Video Demo: [https://youtu.be/B6yIjM1rkIU](https://youtu.be/B6yIjM1rkIU)
#### Description:

`gfr` is a powerful command-line tool designed to streamline your Git and GitHub workflows, especially for projects involving microservices managed as Git submodules. It automates common tasks like repository creation, branch management, releases, and more, letting you focus on coding.

###### This was created without git flow and only with the main branch 🪖😐🪻

## Installation

You can install `gfr` in two ways:

### 1. From PyPI

The easiest way to install `gfr` is directly from the Python Package Index (PyPI).
```
pip install gfr
```

### 2. From Source

Alternatively, you can clone the repository and install it locally. This is useful if you want to contribute to the project.
```
git clone https://github.com/rahmasir/gfr
cd gfr
pip install .
```

## Configuration

Before using `gfr`, you need to create a `.env` file in the root directory of your project. This file stores your GitHub credentials securely.

1.  Create a file named `.env`.
    
2.  Add the following variables:
    
```
# .env
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_ORGANIZATION=your_github_organization
GITHUB_USERNAME=your_github_username
```

-   **`GITHUB_TOKEN`**: A [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens "null") with `repo` scopes.
    
-   **`GITHUB_ORGANIZATION`**: The name of your GitHub organization where repositories will be managed.
    
-   **`GITHUB_USERNAME`**: Your GitHub username, used for assigning issues and pull requests.
    

## Usage

All commands are run through the `ggg` entry point.

### Project & Repository Management

#### `ggg init`

Initializes a new project in an empty directory. This command will:

1.  Create a new repository on GitHub.
    
2.  Initialize a local Git repository.
    
3.  Create and push `develop` and `doc` branches.
    
4.  Set `develop` as the default branch on GitHub.
    
5.  Switch your local branch to `develop`.
    
```
# Navigate to an empty directory
mkdir my-new-project && cd my-new-project

# Run the command and follow the prompts
ggg init
```

#### `ggg create`

Creates a new GitHub repository and immediately clones it into your current directory.
```
ggg create
```

#### `ggg clone`

Fetches a list of all repositories from your organization and provides an interactive menu to choose which one to clone.
```
ggg clone
```

#### `ggg addmicro [microservice-name]` (alias: `am`)

Creates a new repository for an existing local directory and adds it to your main project as a Git submodule.
```
# Assuming 'user-service' is an existing directory
ggg addmicro user-service
```

### Daily Workflow Commands

#### `ggg status`

Displays a detailed, color-coded status for the parent project and all submodules, showing the current branch and lists of staged, unstaged, and untracked files.
```
ggg status
```

#### `ggg add [service] [files...]`

Stages changes in either the parent project or a specific microservice.

-   **`service`**: The target repository.
    
    -   `.`: The parent project.
        
    -   `-`: The last used microservice.
        
    -   `[name]`: The name of a specific microservice.
        
-   **`files...`**: The files to stage (e.g., `.` for all).
    
```
# Stage all changes in the parent project
ggg add . .

# Stage a specific file in the 'user-service'
ggg add user-service src/main.py

# Stage all changes in the last used microservice
ggg add - .
```

#### `ggg commit [service] "[message]"`

Commits staged changes. If committing to a microservice on a feature/bugfix branch, it automatically prepends the issue number to the commit message.
```
# Commit in the parent project
ggg commit . "Initial commit"

# Commit in the 'user-service'
ggg commit user-service "Implement user login endpoint"
```

#### `ggg ac [service] "[message]"`

A convenient shortcut that stages all changes (`add .`) and commits them in one step.
```
ggg ac user-service "Refactor user model"
```

#### `ggg push`

Pushes all branches (`git push --all`) for the parent project and every submodule.
```
ggg push
```

#### `ggg acp [service] "[message]"`

The ultimate shortcut: stages all changes, commits, and pushes everything in a single command.
```
ggg acp . "Update project README"
```

### Branching & Feature Management

#### `ggg feature [service] start "[name]"`

Starts a new feature workflow. It will:

1.  Create a new issue on GitHub with the `enhancement` label.
    
2.  Create a new local branch named `feature/[issue-number]-[feature-name]`.
    
3.  Switch you to the new branch.
    
```
ggg feature . start "User Profile Page"
```

#### `ggg feature [service] finish`

Finishes the current feature branch. It automates the entire closing process:

1.  Pushes the branch to the remote.
    
2.  Creates a pull request to `develop`.
    
3.  Merges the pull request, which automatically closes the associated issue.
    
4.  Deletes the local and remote feature branches.
    
5.  Switches you back to the `develop` branch.
    
```
ggg feature . finish
```

#### `ggg bugfix [service] start "[name]"` / `finish`

Works exactly like the `feature` command but uses the `bugfix` prefix for branches and the `bug` label for issues.
```
ggg bugfix user-service start "Fix login authentication error"
ggg bugfix user-service finish
```

#### `ggg dev` / `ggg doc`

Quickly switch to the `develop` or `doc` branch in the current repository.
```
ggg dev
```

### Release Management

#### `ggg release [service] start`

Initiates the release process. It will:

1.  Determine the next version number (major/minor) based on existing Git tags.
    
2.  Create a new `release/[version]` branch.
    
3.  Prompt you for changelog entries.
    
4.  Create or update the `CHANGELOG.md` file.
    
```
ggg release . start
```

#### `ggg release [service] finish`

Finalizes and publishes a release. This command will:

1.  Create and merge pull requests to both `main` and `develop`.
    
2.  Create a new version tag on the `main` branch.
    
3.  Generate a new GitHub Release with detailed notes and a link to the commits.
    
4.  Clean up the release branch.
    
5.  Switch you back to `develop`.
    
```
ggg release . finish
```

### Utility Commands

#### `ggg link`

Displays a table with clickable GitHub links for the parent project and all submodules.
```
ggg link
```

#### `ggg addasset [service] [asset-name] [destination-file]`

Creates a new file from a predefined template.
```
# Create a MIT LICENCE in user-service
ggg addasset user-service mit LICENCE
```

## How It Works

`gfr` is built on a few core principles to keep it robust and extensible:

-   **Git Submodules**: The tool is designed to work with a microservice architecture where each service is a Git submodule within a parent repository. Commands intelligently target either the parent or a specific submodule.
    
-   **State Management**: A `.gfr.yml` file is created at the root of your project to store simple state, such as the last-used microservice. This enables convenient shortcuts like using `-` as a service name.
    
-   **Modular Commands**: Each command (`add`, `commit`, `release`, etc.) is a self-contained module. This makes the codebase easy to navigate and allows for new commands to be added without affecting existing ones.
    
-   **Service Layers**: The tool separates concerns into different layers. Commands handle user interaction, helpers contain shared business logic, and utilities provide low-level wrappers around Git and the GitHub API.
    

## Contributing

Contributions are welcome! If you have an idea for a new feature or have found a bug, please open an issue. If you'd like to contribute code, please follow these steps:

1.  Fork the repository.
    
2.  Create a new branch for your feature (`git checkout -b feature/AmazingFeature`).
    
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
    
4.  Push to the branch (`git push origin feature/AmazingFeature`).
    
5.  Open a pull request.
    

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
