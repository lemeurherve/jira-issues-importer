#!/usr/bin/env python3

from collections import namedtuple
import os.path
from project import Project
from importer import Importer
from labelcolourselector import LabelColourSelector
from utils import read_xml_files
from config import load_config

config = load_config([
    ("file_names", "JIRA_MIGRATION_FILE_PATHS", "Path to Jira XML query file (semi-colon separate for multiple)", None),
    ("name", "JIRA_MIGRATION_JIRA_PROJECT_NAME", "Jira project name", "INFRA"),
    ("jira_done_id", "JIRA_MIGRATION_JIRA_DONE_ID", "Jira Done statusCategory ID", "3"),
    ("jira_base_url", "JIRA_MIGRATION_JIRA_URL", "Jira base url", "https://issues.jenkins.io"),
    ("github_account", "JIRA_MIGRATION_GITHUB_NAME", "GitHub account name (user/org)", "jenkins-infra"),
    ("github_repo", "JIRA_MIGRATION_GITHUB_REPO", "GitHub repository name", "helpdesk"),
    ("github_pat", "JIRA_MIGRATION_GITHUB_ACCESS_TOKEN", "GitHub Personal Access Token", None),
    ("hosted_artifact_org_repo", "JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO", "Hosted artifacts org/repo", None),
])

print(f"Jira Migration Tool - version {config.version}")

# "org/repo" hosting artifacts like avatars, attachments and username mappings
# If not set, will use local files, and won't add avatar in issues or comments
# Example of such repo: https://github.com/lemeurherve/artifacts-from-jira-issues-example
if not config.hosted_artifact_org_repo:
    print('JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO is not set: no mapping files will be retrieved, no avatar will be rattached to issues or comments, and attachment links won\'t be replaced')

all_xml_files = read_xml_files(config.file_names)

print(
    f'Parameters taken in account:\n'
    f'- XML file:                    {config.file_names}\n'
    f'- Jira project name:           {config.name}\n'
    f'- Jira Done statusCategory ID: {config.jira_done_id}\n'
    f'- Jira base url:               {config.jira_base_url}\n'
    f'- GitHub account name:         {config.github_account}\n'
    f'- GitHub repository name:      {config.github_repo}\n'
    f'- Hosted artifacts org/repo:   {config.hosted_artifact_org_repo}\n'
    f'- Dry-run:                     {config.dry_run}\n'
)

start_from_issue = input('Start from [default "0" (beginning)]: ') or '0'

project = Project(config)
project.load_mappings()

for f in all_xml_files:
    for item in f.channel.item:
        project.add_item(item)

project.prettify()

input('Press any key to begin...')

'''
Steps:
  1. Create any milestones
  2. Create any labels
  3. Create each issue with comments, linking them to milestones and labels
'''
importer = Importer(project)
colourSelector = LabelColourSelector(project)

importer.import_milestones()

if int(start_from_issue) == 0:
    importer.import_labels(colourSelector)

importer.import_issues(int(start_from_issue))
# importer.post_process_comments()
