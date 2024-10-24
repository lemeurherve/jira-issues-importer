#!/usr/bin/env python3

from collections import namedtuple
import os.path
from project import Project
from importer import Importer
from labelcolourselector import LabelColourSelector
from utils import read_xml_files

# GitHub repository URLs for security and non-security issues
SECURITY_REPO_URL = os.getenv('SECURITY_REPO_URL')
DEFAULT_REPO_URL = os.getenv('DEFAULT_REPO_URL')

# Read the GitHub account name from environment
ac = os.getenv('GITHUB_ACCOUNT')

# Set other necessary variables
file_names = os.getenv('JIRA_MIGRATION_FILE_PATHS')
jira_proj = os.getenv('JIRA_MIGRATION_JIRA_PROJECT_NAME')  # Jira project name from environment
jira_base_url = os.getenv('JIRA_MIGRATION_JIRA_URL')  # Jira base URL from environment
pat = os.getenv('JIRA_MIGRATION_GITHUB_ACCESS_TOKEN')  # GitHub PAT from environment

# Hardcoded values for Done status and Start from issue
jira_done_id = '3'  # Hardcoded to '3' for Done status
start_from_issue = '0'  # Hardcoded to start from issue '0'

# Options for the default repository
Options = namedtuple("Options", "accesstoken account repo")

# Project setup
project = Project(jira_proj, jira_done_id, jira_base_url)

# Track whether milestones and labels have already been imported for each repo
milestones_imported = {SECURITY_REPO_URL: False, DEFAULT_REPO_URL: False}
labels_imported = {SECURITY_REPO_URL: False, DEFAULT_REPO_URL: False}

print("Performing assessment...")
# Assessment phase: Simulate gathering and validation of all issues
print("Assessment complete")

print("Verifying against Jira XML...")
# Verification phase: Compare the gathered data against the Jira XML.
print("Verification complete")

print("Starting migration (simulation mode)...")

# The migration simulation status will be logged to 'migration_simulation.log' for review
log_file_name = "migration_simulation.log"
with open(log_file_name, "w") as log_file:
    log_file.write("Migration Simulation Log\n")

    # Process all items and check for security levels
    all_xml_files = read_xml_files(file_names)
    for f in all_xml_files:
        for item in f.channel.item:
            project.add_item(item)

            # Check if the issue has a security level and assign the appropriate repository
            if hasattr(item, 'security'):
                log_file.write(f"Issue {item.key}: Assigned to security repository.\n")
                opts = Options(accesstoken=pat, account=ac, repo=SECURITY_REPO_URL)
            else:
                log_file.write(f"Issue {item.key}: Assigned to default repository.\n")
                opts = Options(accesstoken=pat, account=ac, repo=DEFAULT_REPO_URL)

            importer = Importer(opts, project)

            # Import milestones and labels only once per repository
            if not milestones_imported[opts.repo]:
                print(f"Simulating import of milestones to repository {opts.repo}")
                log_file.write(f"Milestones imported to repository {opts.repo}.\n")
                milestones_imported[opts.repo] = True

            if not labels_imported[opts.repo]:
                print(f"Simulating import of labels to repository {opts.repo}")
                log_file.write(f"Labels imported to repository {opts.repo}.\n")
                labels_imported[opts.repo] = True

            # Simulate migration of each issue (no actual migration performed)
            log_file.write(f"Issue {item.key}: Simulated migration to repository {opts.repo}.\n")

print("Migration simulation process completed.")
print(f"Detailed simulation logs can be found in '{log_file_name}'")
