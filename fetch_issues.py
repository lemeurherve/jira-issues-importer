#!/usr/bin/env python3

"""
This module fetches Jira issues using a specified JQL query and processes them.
It supports pagination and handles security level filtering.
"""

import os
import urllib.parse  # Standard library
from math import ceil  # Standard library

# noinspection PyUnresolvedReferences
from lxml import etree, objectify  # Third-party libraries
import requests  # Third-party libraries

jira_server = os.getenv('JIRA_MIGRATION_JIRA_URL', 'https://issues.jenkins.io')
jql_query = os.getenv('JIRA_MIGRATION_JQL_QUERY')
FILE_PATH = 'jira_output'  # Changed file_path to uppercase to follow constant naming convention

encoded_query = urllib.parse.quote(jql_query)
pager = 0

def fetch_total_results():
    """
    Load one result from query to see how many results there will be to calculate pagination.
    """
    max_results_local = 1  # Renamed to avoid conflicts
    url = f'{jira_server}/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?jqlQuery={encoded_query}&tempMax={max_results_local}&pager/start={max_results_local}'

    # Print the URL for debugging
    print("Final URL:", url)

    response = requests.get(url)

    # Print the response text to check its content
    print("Response Text:", response.text)

    result = objectify.fromstring(response.text)
    total_results = int(result.channel.issue.attrib['total'])
    return total_results

def has_security_level(issue):
    """
    Check if an issue contains a security level.
    """
    return hasattr(issue, 'security')

# Fetch total results and calculate total pages
total_results = fetch_total_results()
total_pages = ceil(total_results / 1000)

max_results = 1000  # Kept max_results for use in pagination

while pager < total_results:
    page_number = ceil(pager / 1000 + 1)
    print(f'Fetching page {page_number}, out of {total_pages}')
    url = f'{jira_server}/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?jqlQuery={encoded_query}&tempMax={max_results}&pager/start={pager}'
    response = requests.get(url)
    root = objectify.fromstring(response.text)
    
    for item in root.channel.item:
        # Check for Security Level
        if has_security_level(item):
            print(f"Issue {item.key} has a security level: {item.security}")

    with open(f'{FILE_PATH}/result-{pager}.xml', 'wb') as doc:
        doc.write(etree.tostring(root, pretty_print=True))
    pager += max_results

print('Complete')
