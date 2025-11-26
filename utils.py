from lxml import objectify
import os
import glob
import requests

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
