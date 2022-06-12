#!/usr/bin/env python3

from collections import namedtuple
import os.path
from project import Project
from importer import Importer
from labelcolourselector import LabelColourSelector
from utils import read_xml_files

file_names = os.getenv('JIRA_MIGRATION_FILE_PATHS') or input(
    'Path to Jira XML query file (semi-colon separate for multiple files, directories are accepted): ')
all_xml_files = read_xml_files(file_names)

jira_proj = os.getenv('JIRA_MIGRATION_JIRA_PROJECT_NAME') or input('Jira project name: ') or 'INFRA'
jira_done_id = os.getenv('JIRA_MIGRATION_JIRA_DONE_ID') or input('Jira Done statusCategory ID [default "3"]: ') or '3'
jira_base_url = os.getenv('JIRA_MIGRATION_JIRA_URL') or input('Jira base url [default "https://issues.jenkins.io"]: ') or 'https://issues.jenkins.io'
ac = os.getenv('JIRA_MIGRATION_GITHUB_NAME') or input('GitHub account name (user/org): ') or 'jenkins-infra'
repo = os.getenv('JIRA_MIGRATION_GITHUB_REPO') or input('GitHub repository name: ') or 'helpdesk'
pat = os.getenv('JIRA_MIGRATION_GITHUB_ACCESS_TOKEN') or input('Github Personal Access Token: ') # or '<your-github-pat>'
start_from_issue = input('Start from [default "0" (beginning)]: ') or '0'

Options = namedtuple("Options", "accesstoken account repo")
opts = Options(accesstoken=pat, account=ac, repo=repo)

project = Project(jira_proj, jira_done_id, jira_base_url)

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
  4: Post-process all comments to replace issue id placeholders with the real ones
'''
importer = Importer(opts, project)
colourSelector = LabelColourSelector(project)

importer.import_milestones()

if int(start_from_issue) == 0:
    importer.import_labels(colourSelector)

importer.import_issues(int(start_from_issue))
# importer.post_process_comments()
