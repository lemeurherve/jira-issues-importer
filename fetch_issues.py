#!/usr/bin/env python3

import os
import urllib.parse
# noinspection PyUnresolvedReferences
from lxml import etree, objectify

import requests
from math import ceil

jira_server = os.getenv('JIRA_MIGRATION_JIRA_URL', 'https://issues.jenkins.io')
jql_query = os.getenv('JIRA_MIGRATION_JQL_QUERY')
max_results = int(os.getenv('JIRA_MIGRATION_JQL_MAX_RESULTS', 1000))
file_path = 'jira_output'

try:
    os.makedirs(file_path)
except FileExistsError:
    # directory already exists
    pass

encoded_query = urllib.parse.quote(jql_query)
pager = 0


def fetch_total_results():
    """
    Load one result from query to see how many results there will be to calculate pagination.
    """
    global url, response, total_results
    url = f'{jira_server}/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?jqlQuery={encoded_query}&tempMax=1&pager/start=1'
    response = requests.get(url)
    result = objectify.fromstring(response.text)
    return int(result.channel.issue.attrib['total'])


total_results = fetch_total_results()
total_pages = ceil(total_results / max_results)

while pager < total_results:
    page_number = ceil(pager / max_results + 1)
    print(f'Fetching page {page_number}, out of {total_pages}')
    url = f'{jira_server}/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?jqlQuery={encoded_query}&tempMax={max_results}&pager/start={pager}'
    response = requests.get(url)
    root = objectify.fromstring(response.text)

    with open(f'{file_path}/result-{pager}.xml', 'wb') as doc:
        doc.write(etree.tostring(root, pretty_print=True))
    pager += max_results

print('Complete')

print(
    '\n\n'
    'Before running main.py, you should execute ./concatenate-xml-results.sh script\n'
    'then ./retrieve-watchers-and-remotelinks.sh (or ./retrieve-remotelinks.sh if you don\'t have permissions to see watchers)\n'
)
