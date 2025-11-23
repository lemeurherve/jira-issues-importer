from lxml import objectify
import os
import glob
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

# Ex of line: JIRAUSER134221:hlemeur
def fetch_jira_fixed_usernames(filename):
    with open(filename) as file:
        entry = [line.split(":") for line in file.readlines()]
    return {key.strip(): value.strip() for key, value in entry}

# Ex of line: hlemeur:avatars/hlemeur.png
def fetch_jira_user_avatars(filename):
    with open(filename) as file:
        entry = [line.split(":") for line in file.readlines()]
    return {key.strip(): value.strip() for key, value in entry}

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
