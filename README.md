# Jira Issue Migrator

Jira Issue Migrator is a Python-based tool designed to migrate issues from Jira to GitHub. The script handles both standard and security-level issues by simulating and later performing the migration process. It includes support for importing milestones, labels, and issues from Jira to the respective GitHub repositories.

## Features

- **Issue Migration**: Simulates and migrates Jira issues to GitHub repositories.
- **Security-level Handling**: Issues with specific security levels can be migrated to a separate GitHub repository.
- **Milestone and Label Import**: Imports milestones and labels for each repository during migration.
- **Simulation Mode**: Simulates the migration process for validation before performing the actual migration.
- **Detailed Logs**: Provides a log file (`migration_simulation.log`) containing the detailed status of each issue migration.

## Files

- `main.py`: The main script responsible for orchestrating the migration.
- `run_migration.sh`: Bash wrapper script to automate environment setup and run the migration script.
- `fetch_issues.py`: Script to fetch Jira issues for migration.
- `fetch_labels.py`: Script to fetch labels associated with Jira issues.
- `importer.py`: Handles the actual import process of issues, milestones, and labels.
- `labelcolourselector.py`: Assists in assigning colors to GitHub labels.
- `project.py`: Manages the migration project, including Jira project details.
- `utils.py`: Contains utility functions for reading Jira XML files.
- `requirements.txt`: Lists the Python dependencies for the migration scripts.

## Prerequisites

- Python 3.x
- A GitHub personal access token (PAT), **classic**, with access to the relevant repositories.
- Jira XML export of issues to be migrated.

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/jira-issue-migrator.git
cd jira-issue-migrator
pip install -r requirements.txt
```

## Usage

1. **Prepare your environment:**

   Ensure the Jira XML export file is in the same directory as the scripts. No need to provide an explicit path; the script will auto-detect the XML file. 

2. **Run the migration script using the bash wrapper:**

   Use the `run_migration.sh` script to run the migration simulation and provide the necessary arguments:

   ```bash
   ./run_migration.sh -p <JIRA_PROJECT> -u <JIRA_URL> -g <GITHUB_ACCOUNT> -s <SECURITY_REPO_NAME> -r <DEFAULT_REPO_NAME>
   ```

   Example:

   ```bash
   ./run_migration.sh -p CIMANAGE -u jira.example.com -g your-org -s security-repo -r default-repo
   ```

   This will perform an assessment, verify the Jira XML export, and simulate the migration. A log of the simulation can be found in `migration_simulation.log`.

3. **Review the simulation log:**

   Ensure the migration logic is correct by reviewing the `migration_simulation.log`.

4. **Perform the actual migration (when ready):**

   After validating the simulation, you can modify the script to perform the actual migration.

## Logging

A detailed log of each migration simulation is saved in `migration_simulation.log` file. This file includes the status of each milestone, label, and issue migration for review before performing the actual migration.
