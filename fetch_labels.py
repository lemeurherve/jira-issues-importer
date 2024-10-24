#!/usr/bin/env python3
import os
from project import Project
from utils import read_xml_files

# Fetch environment variables for Jira project details and file paths
jira_proj = os.getenv('JIRA_MIGRATION_JIRA_PROJECT_NAME')
jira_done_id = os.getenv('JIRA_MIGRATION_JIRA_DONE_ID')
jira_base_url = os.getenv('JIRA_MIGRATION_JIRA_URL')
file_names = os.getenv('JIRA_MIGRATION_FILE_PATHS')

# Initialize the Project object
project = Project(jira_proj, jira_done_id, jira_base_url)

# Read the Jira XML files
all_xml_files = read_xml_files(file_names)

# Add each item (issue) to the project and collect labels
for f in all_xml_files:
    for item in f.channel.item:
        project.add_item(item)

# Print out all collected labels in alphabetical order
[print(key) for key in sorted(project.get_labels().keys())]
