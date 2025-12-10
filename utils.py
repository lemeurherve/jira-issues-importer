from lxml import objectify
import os
import glob
import requests
import re

from collections import defaultdict

def fetch_labels_mapping():
    with open('labels_mapping.txt') as file:
        entry = [line.split("=") for line in file.readlines()]
    return {key.strip(): value.strip() for key, value in entry}


def fetch_allowed_labels():
    with open('allowed_labels.txt') as file:
        return [line.strip('\n') for line in file.readlines()]

def fetch_remote_links():
    groups = defaultdict(list)

    with open('combined-remotelinks.txt', "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            key = line.split(":", 1)[0]
            link = line.split(":", 1)[1]
            groups[key].append(link)

    return dict(groups)

def fetch_hosted_mappings(project):
    """
    Downloads the Jira mapping files and updates the project instance.
    """

    mapping_folder = os.path.abspath('./' + project.mapping_foldername)
    fresh = True
    if os.path.exists(mapping_folder):
        reply = input("Start with fresh mapping files? [Y/n]: ").strip().lower()
        fresh = (reply != "n")
    else:
        os.makedirs(mapping_folder)

    # Ex of line: JIRAUSER134221:hlemeur
    project.jira_fixed_usernames = _download_mapping(project.hosted_artifact_base, mapping_folder, project.jira_fixed_username_filename, fresh)
    # Ex of line: hlemeur:avatars/hlemeur.png
    project.jira_user_avatars = _download_mapping(project.hosted_artifact_base, mapping_folder, project.jira_username_avatar_mapping_filename, fresh)
    # Ex of line: 64966:jenkinsci/attachments-from-jira-issues-core-cli/refs/heads/main/attachments/64966/jenkins-build3.log
    project.jira_attachments = _download_mapping(project.hosted_artifact_base, mapping_folder, project.jira_attachments_filename, fresh)

    return project

def _download_mapping(mapping_base_url, mapping_folder, mapping_filename, force = False):
    """
    Downloads one mapping file if necessary and returns a parsed dict.
    """

    folder_name = os.path.basename(mapping_folder)

    url = f'{mapping_base_url}/{folder_name}/{mapping_filename}'
    dest = os.path.join(mapping_folder, mapping_filename)

    if force and os.path.exists(dest):
        print(f'- Deleting existing {dest}')
        os.remove(dest)

    if not os.path.exists(dest):
        print(f'- Downloading: {url}')
        r = requests.get(url)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
    else:
        print(f'- Using cached mapping: {dest}')

    return _parse_mapping(dest)

def _parse_mapping(path):
    mapping = {}

    if not os.path.exists(path):
        return mapping

    with open(path) as f:
        for line in f:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            mapping[key.strip()] = value.strip()

    return mapping

def _map_label(label, labels_mapping):
    if label in labels_mapping:
        return labels_mapping[label]
    else:
        return label

def _is_label_approved(label, approved_labels):
    return label in approved_labels


def convert_label(label, labels_mappings, approved_labels):
    mapped_label = _map_label(label, labels_mappings)

    if _is_label_approved(mapped_label, approved_labels):
        return mapped_label
    return None

def proper_label_str(label):
    return label.lower().strip().replace(' ', '-').replace("'", '')

def read_xml_file(file_path):
    with open(file_path) as file:
        return objectify.fromstring(file.read())

def read_xml_files(file_path):
    files = list()
    for file_name in file_path.split(';'):
        if os.path.isdir(file_name):
            xml_files = glob.glob(file_name + '/*.xml')
            for file in xml_files:
                files.append(read_xml_file(file))
        else:
            files.append(read_xml_file(file_name))

    return files


# TODO: match a list of project names (ex: JENKINS, INFRA, etc.) instead of just the current one
def replace_jira_urls_with_redirection_service(project, content):
    """
    Replace Jira browse URLs with redirection service URLs if configured.
    Preserves query strings from the original URLs.
    Excludes links marked with 'original-jira-link' class.

    Example: https://issues.jenkins.io/browse/JENKINS-123?focusedId=456
                -> https://issue-redirect.jenkins.io/issue/123?focusedId=456
    """
    if content is None or not project.config.redirection_service:
        return content if content is not None else ''

    # Pattern to match any Jira browse URL (with or without https://)
    # Uses negative lookbehind to exclude 'original-jira-link' class links
    # Multiple lookbehinds handle cases with/without protocol in the href attribute
    # Remove protocol from jiraBaseUrl since we'll add an optional one
    jira_base_without_protocol = project.jiraBaseUrl.replace('https://', '').replace('http://', '')
    escaped_jira_base_url = jira_base_without_protocol.replace('.', r'\.')
    pattern = (
        rf'(?<!<a class="original-jira-link" href=")'
        rf'(?<!<a class="original-jira-link" href="https://)'
        rf'(?<!<a class="original-jira-link" href="http://)'
        rf'(?:https?://)?{escaped_jira_base_url}/browse/{project.name}-(\d+)(\?[^\s<>"]*)?'
    )

    # Replace with redirection service URL + issue number + query string (if present)
    issue_number_and_query = r'\1\2'
    # TODO: use project name when redirection service allows it to allow multiple projects (ex: JENKINS, INFRA)
    # replacement = f'{project.config.redirection_service}/{project.name}/{issue_number_and_query}'
    replacement = f'{project.config.redirection_service}/issue/{issue_number_and_query}'

    return re.sub(pattern, replacement, content)

def get_github_search_or_redirect_url_from_jira_key(project, jira_key):
    """
    Returns the GitHub search URL or redirection service URL for a given Jira key.
    """
    jira_id = jira_key.split("-")[1]
    url = f'https://github.com/search?q=org%3A{project.config.github_account}+%22jira_issue_key%3D{jira_key}%22&type=issues'
    if project.config.redirection_service:
        # TODO: use project name when redirection service allows it to allow multiple projects (ex: JENKINS, INFRA)
        url = f'{project.config.redirection_service}/issue/{jira_id}'
    return f'<a class="jira-relationship" href="{url}">{jira_key}</a>'


# TODO: match a list of project names (ex: JENKINS, INFRA, etc.) instead of just the current one
def replace_plain_jira_keys_with_links(project, content):
    """
    Replace plain text issue key references with markdown links.

    Use redirection service if set.

    Example: Plain text "JENKINS-123" -> [JENKINS-123](https://issue-redirect.jenkins.io/issue/123)

    Excludes keys that are:
    - Already part of a URL
    - Already in a markdown or HTML link
    """
    if content is None or not project.config.redirection_service:
        return content if content is not None else ''

    # Pattern to match plain text issue key references
    # Excludes keys already part of URLs or links
    plain_key_pattern = (
        rf'(?<!browse/)'  # Not after browse/
        rf'(?<!href=")'  # Not after href="
        rf'(?<!\[)'  # Not after [
        rf'(?<!\()'  # Not after (
        rf'(?<!>)'  # Not after > (inside HTML tags)
        rf'\b({project.name}-(\d+))\b'  # Match whole word PROJECT-NUMBER
        rf'(?!\])'  # Not before ]
        rf'(?!\))'  # Not before )
    )

    def replace_plain_key(match):
        full_key = match.group(1)
        issue_number = match.group(2)
        if project.config.redirection_service:
            # TODO: use project name when redirection service allows it to allow multiple projects (ex: JENKINS, INFRA)
            # link_url = f'{self.config.redirection_service}/{self.name}/{issue_number}'
            link_url = f'{project.config.redirection_service}/issue/{issue_number}'
        else:
            link_url = f'{project.jiraBaseUrl}/browse/{full_key}'
        return f'<a class="jira-plain-text-key" href="{link_url}">{full_key}</a>'

    return re.sub(plain_key_pattern, replace_plain_key, content)
