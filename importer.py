import os
import requests
import time
import json
import copy
import re

from utils import fetch_labels_mapping, fetch_allowed_labels, convert_label

class FakeResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 202
        self.headers = {}

    def json(self):
        return self._data

class Importer:
    _GITHUB_ISSUE_PREFIX = "INFRA-"
    _PLACEHOLDER_PREFIX = "@PSTART"
    _PLACEHOLDER_SUFFIX = "@PEND"
    _DEFAULT_TIME_OUT = 120.0

    def __init__(self, project):
        self.project = project
        self.jira_to_github_txt_mapping = f'jira-keys-to-github-id_{self.project.current_datedime}.txt'
        self.jira_to_complete_github_txt_mapping = f'jira-keys-to-github-id-for-external-use_{self.project.current_datedime}.txt'
        self.github_api_url = f'https://api.github.com/repos/{self.project.config.github_account}/{self.project.config.github_repo}'
        self.jira_issue_replace_patterns = {
            'https://issues.jenkins.io/browse/%s%s' % (self.project.name, r'-(\d+)'): r'\1',
            self.project.name + r'-(\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1',
            r'Issue (\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1'}
        self.headers = {
            'Accept': 'application/vnd.github.golden-comet-preview+json',
            'Authorization': f'token {self.project.config.github_pat}'
        }
        self._dry_run_issue_counter = -1
        self._dry_run_index_data = []

    def import_milestones(self):
        """
        Imports the gathered project milestones into GitHub and remembers the created milestone ids
        """
        milestone_url = self.github_api_url + '/milestones'
        print('Importing milestones...', milestone_url)
        print

        if self.project.config.dry_run:
            print('Dry-run: no milestone import to GitHub')

        # Check existing first
        existing = list()

        def get_milestone_list(url):
            return requests.get(url, headers=self.headers,
                                timeout=Importer._DEFAULT_TIME_OUT)

        def get_next_page_url(url):
            return url.replace('<', '').replace('>', '').replace('; rel="next"', '')

        milestone_pages = list()
        ms = get_milestone_list(milestone_url + '?state=all')
        milestone_pages.append(ms.json())

        if 'Link' in ms.headers:
            links = ms.headers['Link'].split(',')
            nextPageUrl = get_next_page_url(links[0])

            while nextPageUrl is not None:
                time.sleep(1)
                nextPageUrl = None

                for l in links:
                    if 'rel="next"' in l:
                        nextPageUrl = get_next_page_url(l)

                if nextPageUrl is not None:
                    ms = get_milestone_list(nextPageUrl)
                    links = ms.headers['Link'].split(',')
                    milestone_pages.append(ms.json())

        for ms_json in milestone_pages:
            for m in ms_json:
                print(self.project.get_milestones().keys())
                try:
                    if m['title'] in self.project.get_milestones().keys():
                        self.project.get_milestones()[m['title']] = m['number']
                        print(m['title'], 'found')
                        existing.append(m['title'])
                except TypeError:
                    pass

        # Export new ones
        for mkey in self.project.get_milestones().keys():
            if mkey in existing:
                continue

            data = {'title': mkey}
            if not self.project.config.dry_run:
                r = requests.post(milestone_url, json=data, headers=self.headers, timeout=Importer._DEFAULT_TIME_OUT)

                # overwrite histogram data with the actual milestone id now
                if r.status_code == 201:
                    content = r.json()
                    self.project.get_milestones()[mkey] = content['number']
                    print(mkey)

    def import_labels(self, colour_selector):
        """
        Imports the gathered project components and labels as labels into GitHub 
        """
        label_url = self.github_api_url + '/labels'
        print('Importing labels...', label_url)
        print()

        if self.project.config.dry_run:
            print('Dry-run: no label import to GitHub')

        for lkey in self.project.get_all_labels().keys():

            prefixed_lkey = lkey.lower()
            # prefix component
            if os.getenv('JIRA_MIGRATION_INCLUDE_COMPONENT_IN_LABELS', 'true') == 'true':
                if lkey in self.project.get_components().keys():
                    prefixed_lkey = 'jira-component:' + prefixed_lkey

            prefixed_lkey = convert_label(prefixed_lkey, self.project.labels_mapping, self.project.approved_labels)
            if prefixed_lkey is None:
                continue

            data = {'name': prefixed_lkey,
                    'color': colour_selector.get_colour(lkey)}
                    
            if not self.project.config.dry_run:
                r = requests.post(label_url, json=data, headers=self.headers, timeout=Importer._DEFAULT_TIME_OUT)
            if r.status_code == 201 or self.project.config.dry_run:
                print(lkey + '->' + prefixed_lkey)
            else:
                print('Failure importing label ' + prefixed_lkey,
                      r.status_code, r.content, r.headers)

    def _find_jira_links(self, text):
        """
        Finds all Jira links in the given text.
        Returns a list of unique Jira links found.
        """
        if not text:
            return []

        jira_links = []

        # Pattern 1: Full Jira URLs like https://issues.jenkins.io/browse/INFRA-123
        # excluding "no-jira-link-rewrite" links
        full_url_pattern = (
            rf'(?<!<a class="no-jira-link-rewrite" href=")'
            rf'{self.project.jiraBaseUrl}/browse/({self.project.name}-\d+)'
        )
        full_urls = re.findall(full_url_pattern, text)
        jira_links.extend(full_urls)

        # Pattern 2: Project key format like INFRA-123
        project_key_pattern = self.project.name + r'-(\d+)'
        project_keys = re.findall(project_key_pattern, text)
        jira_links.extend([f'{self.project.name}-{key}' for key in project_keys])

        # Return unique links
        return list(set(jira_links))

    def _format_issue_as_markdown(self, issue, comments, jira_key):
        """
        Formats an issue and its comments as markdown.
        """
        md = []

        # Title
        md.append(f"# {issue.get('title', 'Untitled')}\n")

        # Metadata
        md.append("## Metadata\n")
        md.append(f"**Jira Key:** {jira_key}\n\n")
        md.append(f"**State:** {issue.get('state', 'open')}\n\n")

        # Labels
        labels = issue.get('labels', [])
        if labels:
            md.append(f"**Labels:** {', '.join(labels)}\n\n")
        else:
            md.append("**Labels:** None\n\n")

        # Milestone
        if 'milestone' in issue:
            md.append(f"**Milestone:** {issue['milestone']}\n\n")

        # Assignee
        if 'assignee' in issue and issue['assignee']:
            md.append(f"**Assignee:** @{issue['assignee']}\n\n")

        # Created at
        if 'created_at' in issue:
            md.append(f"**Created:** {issue['created_at']}\n\n")

        # Closed at
        if 'closed_at' in issue and issue['closed_at']:
            md.append(f"**Closed:** {issue['closed_at']}\n\n")

        # Body
        md.append("## Description\n\n")
        body = issue.get('body', '')
        if body:
            md.append(f"{body}\n\n")
        else:
            md.append("_No description provided_\n\n")

        # Comments
        if comments:
            md.append(f"## Comments ({len(comments)})\n\n")
            for i, comment in enumerate(comments, 1):
                md.append(f"### Comment {i}\n\n")
                if 'created_at' in comment:
                    md.append(f"**Date:** {comment['created_at']}\n\n")
                md.append(f"{comment.get('body', '')}\n\n")
                md.append("---\n\n")

        return ''.join(md)

    def _generate_index_markdown(self):
        """
        Generates an index.md file listing all issues.
        """
        if not self._dry_run_index_data:
            return

        md = []
        md.append("# Issues Index\n\n")
        md.append(f"Total issues: {len(self._dry_run_index_data)}\n\n")

        # Create a table
        md.append("| Jira Key | Title | State | Labels | Created | Closed |\n")
        md.append("|----------|-------|-------|--------|---------|--------|\n")

        for issue_data in self._dry_run_index_data:
            jira_key = issue_data['jira_key']
            title = issue_data['title'].replace('|', '\\|')  # Escape pipes in title
            state = issue_data['state']
            labels = ', '.join(issue_data['labels']) if issue_data['labels'] else '-'
            labels = labels.replace('|', '\\|')  # Escape pipes in labels
            created = issue_data.get('created_at', '-')
            closed = issue_data.get('closed_at', '-')

            # Create a link to the markdown file
            md.append(f"| [{jira_key}]({jira_key}.md) | {title} | {state} | {labels} | {created} | {closed} |\n")

        # Add summary statistics
        md.append("\n## Statistics\n\n")
        open_issues = sum(1 for d in self._dry_run_index_data if d['state'] == 'open')
        closed_issues = sum(1 for d in self._dry_run_index_data if d['state'] == 'closed')
        md.append(f"- **Open:** {open_issues}\n")
        md.append(f"- **Closed:** {closed_issues}\n")

        # Count labels
        all_labels = {}
        for issue_data in self._dry_run_index_data:
            for label in issue_data['labels']:
                all_labels[label] = all_labels.get(label, 0) + 1

        if all_labels:
            md.append("\n## Labels\n\n")
            for label, count in sorted(all_labels.items(), key=lambda x: x[1], reverse=True):
                md.append(f"- **{label}:** {count}\n")

        return ''.join(md)

    def import_issues(self, start_from_count):
        """
        Starts the issue import into GitHub:
        First the milestone id is captured for the issue.
        Then JIRA issue relationships are converted into comments.
        After that, the comments are taken out of the issue and 
        references to JIRA issues in comments are replaced with a placeholder    
        """
        print('Importing issues...')

        if self.project.config.dry_run:
            print('Dry-run: no issue import to GitHub')

        count = 0
        issue_mappings = []
        github_issue_ids = {}

        for issue in self.project.get_issues():
            if start_from_count > count:
                count += 1
                continue

            print("Index = ", count)

            if 'milestone_name' in issue:
                issue['milestone'] = self.project.get_milestones()[
                    issue['milestone_name']]
                del issue['milestone_name']

            original_issue_comments = issue['comments']
            issue_watchers_count = int(issue['_watchers_count'])
            issue_votes_count = int(issue['_votes_count'])

            self.convert_relationships_to_comments(issue)

            issue_comments = issue['comments']
            del issue['comments']
            comments = []
            for comment in issue_comments:
                comments.append(
                    dict((k, self._replace_jira_with_github_id(v)) for k, v in comment.items()))

            self.import_issue_with_comments(issue, comments)

            # Storing if issue and/or comments have Jira links in order to facilitate post-process
            issue_mapping = copy.deepcopy(issue)
            issue_mapping['watchers_count'] = issue_watchers_count
            issue_mapping['has_watchers'] = 'true' if issue_watchers_count > 0 else 'false'
            issue_mapping['votes_count'] = issue_votes_count
            issue_mapping['has_votes'] = 'true' if issue_votes_count > 0 else 'false'
            issue_mapping['jira_links'] = []
            issue_mapping['jira_links_in_body'] = []
            issue_mapping['jira_links_in_comments'] = []
            issue_mapping['has_jira_links'] = []
            issue_mapping['has_jira_links_in_body'] = []

            issue_links = self._find_jira_links(issue_mapping['body'])
            del issue_mapping['body']
            if issue_links:
                issue_mapping['jira_links'] = issue_links
                issue_mapping['jira_links_in_body'] = issue_links
                issue_mapping['has_jira_links'] = 'true'
                issue_mapping['has_jira_links_in_body'] = 'true'

            for comment in original_issue_comments:
                comment_links = self._find_jira_links(comment['body'])
                if comment_links:
                    issue_mapping['jira_links'].extend(comment_links)
                    issue_mapping['jira_links_in_comments'].extend(comment_links)
                    issue_mapping['has_jira_links'] = 'true'
                    issue_mapping['has_jira_links_in_comments'] = 'true'
            issue_mapping['jira_links'] = list(set(issue_mapping['jira_links']))
            issue_mapping['jira_links_in_body'] = list(set(issue_mapping['jira_links_in_body']))
            issue_mapping['jira_links_in_comments'] = list(set(issue_mapping['jira_links_in_comments']))

            issue_mappings.append(issue_mapping)
            github_issue_ids[issue_mapping['jira_issue_key']] = issue_mapping['github_issue_id']

            count += 1

        # Find Jira links that have been imported and that can be rewritten in post-process
        for mapping in issue_mappings:
            if mapping['has_jira_links']:
                mapping['jira_links_imported'] = []
                mapping['jira_links_in_body_imported'] = []
                mapping['jira_links_in_comments_imported'] = []
                for jira_key in mapping['jira_links_in_body']:
                    if jira_key in github_issue_ids:
                        mapping['jira_links_imported'].append(jira_key)
                        mapping['jira_links_in_body_imported'].append(jira_key)
                for jira_key in mapping['jira_links_in_comments']:
                    if jira_key in github_issue_ids:
                        mapping['jira_links_imported'].append(jira_key)
                        mapping['jira_links_in_comments_imported'].append(jira_key)
                mapping['jira_links_imported'] = list(set(mapping['jira_links_imported']))
                mapping['jira_links_in_body_imported'] = list(set(mapping['jira_links_in_body_imported']))
                mapping['jira_links_in_comments_imported'] = list(set(mapping['jira_links_in_comments_imported']))

        # Save collected data to JSON after all issues are imported
        json_mapping = f'jira-to-github-mapping_{self.project.current_datedime}.json'
        with open(json_mapping, 'w', encoding='utf-8') as f:
            json.dump(issue_mappings, f, indent=2, ensure_ascii=False)
        print(json_mapping + ' saved.')
        print('Text mapping: ' + self.jira_to_github_txt_mapping)

        # Generate index.md in dry-run mode
        if self.project.config.dry_run and self._dry_run_index_data:
            index_md = self._generate_index_markdown()
            index_filename = 'dry-run/index.md'
            with open(index_filename, 'w', encoding='utf-8') as f:
                f.write(index_md)
            print(f'Dry-run: saved index to {index_filename}')

    def import_issue_with_comments(self, issue, comments):
        """
        Imports a single issue with its comments into GitHub.
        Importing via GitHub's normal Issue API quickly triggers anti-abuse rate limits.
        So their unofficial Issue Import API is used instead:
        https://gist.github.com/jonmagic/5282384165e0f86ef105
        This is a two-step process:
        First the issue with the comments is pushed to GitHub asynchronously.
        Then GitHub is pulled in a loop until the issue import is completed.
        Finally the issue github is noted.    
        """
        print('Issue ', issue['key'])
        print('Labels', issue['labels'])
        jira_key = issue['key']
        del issue['key']

        response = self.upload_github_issue(issue, comments, jira_key)
        status_url = response.json()['url']
        gh_issue_url = self.wait_for_issue_creation(status_url).json()['issue_url']
        gh_issue_id = int(gh_issue_url.split('/')[-1])
        issue['github_issue_id'] = gh_issue_id
        issue['jira_issue_key'] = jira_key

        jira_gh = f"{jira_key}:{gh_issue_id}\n"
        jira_complete_gh = f"{jira_key}:{self.project.config.github_account}/{self.project.config.github_repo}#{gh_issue_id}\n"
        with open(self.jira_to_github_txt_mapping, 'a') as f:
            f.write(jira_gh)
        with open(self.jira_to_complete_github_txt_mapping, 'a') as f:
            f.write(jira_complete_gh)

    def upload_github_issue(self, issue, comments, jira_key):
        """
        Uploads a single issue to GitHub asynchronously with the Issue Import API.
        In dry-run mode, saves the issue data to a JSON file in the dry-run folder.
        """
        issue_url = self.github_api_url + '/import/issues'
        # Delete keys starting with "_", only there for data gathering, not for issue upload
        for key in list(issue):
            if key.startswith('_'):
                issue.pop(key)
        issue_data = {'issue': issue, 'comments': comments}

        if self.project.config.dry_run:
            # Create dry-run folder if it doesn't exist
            dry_run_folder = 'dry-run'
            os.makedirs(dry_run_folder, exist_ok=True)

            # Save issue data to JSON file
            json_filename = os.path.join(dry_run_folder, f'{jira_key}.json')
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(issue_data, f, indent=2, ensure_ascii=False)
            print(f'Dry-run: saved issue data to {json_filename}')

            # Save issue as markdown file
            md_content = self._format_issue_as_markdown(issue, comments, jira_key)
            md_filename = os.path.join(dry_run_folder, f'{jira_key}.md')
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            print(f'Dry-run: saved issue markdown to {md_filename}')

            # Collect data for index
            self._dry_run_index_data.append({
                'jira_key': jira_key,
                'title': issue.get('title', 'Untitled'),
                'state': issue.get('state', 'open'),
                'labels': issue.get('labels', []),
                'created_at': issue.get('created_at', ''),
                'closed_at': issue.get('closed_at', '')
            })

            return FakeResponse({'url': 'dry_run'})

        response = requests.post(issue_url, json=issue_data, headers=self.headers,
            timeout=Importer._DEFAULT_TIME_OUT)
        if response.status_code == 202:
            return response
        elif response.status_code == 422:
            raise RuntimeError(
                "Initial import validation failed for issue '{}' due to the "
                "following errors:\n{}".format(issue['title'], response.json())
            )
        else:
            raise RuntimeError(
                "Failed to POST issue at {}: '{}' due to unexpected HTTP status code: {}\nerrors:\n{}"
                .format(issue_url, issue['title'], response.status_code, response.json())
            )

    def wait_for_issue_creation(self, status_url):
        """
        Check the status of a GitHub issue import.
        If the status is 'pending', it sleeps, then rechecks until the status is
        either 'imported' or 'failed'.
        """
        if self.project.config.dry_run:
            fake_id = self._dry_run_issue_counter
            self._dry_run_issue_counter += -1
            return FakeResponse({'issue_url': f'dry_run/{fake_id}'})

        while True:  # keep checking until status is something other than 'pending'
            time.sleep(3)
            response = requests.get(status_url, headers=self.headers, 
                timeout=Importer._DEFAULT_TIME_OUT)
            if response.status_code == 404:
                continue
            elif response.status_code != 200:
                raise RuntimeError(
                    "Failed to check GitHub issue import status url: {} due to unexpected HTTP status code: {}"
                    .format(status_url, response.status_code)
                )

            status = response.json()['status']
            if status != 'pending':
                break

        if status == 'imported':
            print("Imported Issue:", response.json()['issue_url'].replace('api.github.com/repos/', 'github.com/'))
        elif status == 'failed':
            raise RuntimeError(
                "Failed to import GitHub issue due to the following errors:\n{}"
                .format(response.json())
            )
        else:
            raise RuntimeError(
                "Status check for GitHub issue import returned unexpected status: '{}'"
                .format(status)
            )
        return response

    def convert_relationships_to_comments(self, issue):
        duplicates = issue['duplicates']
        is_duplicated_by = issue['is-duplicated-by']
        relates_to = issue['is-related-to']
        depends_on = issue['depends-on']
        blocks = issue['blocks']
        try:
            epic_key = issue['epic-link']
        except (AttributeError, KeyError):
            epic_key = None

        def _comment_body(jira_key, relationship_type):
            return (
                f'<!-- ### Imported Jira references for easier searching -->\n'
                f'<!-- [synthetic_comment=relationship] -->\n'
                f'<!-- [jira_relationship_key={jira_key}] -->'
                f'<!-- [jira_relationship_type={relationship_type}] -->\n'
                f'<i>[Original `{relationship_type}` from Jira: <a href="https://github.com/{self.project.config.github_account}/{self.project.config.github_repo}/issues?q=is%3Aissue%20%22jira_issue_key%3D{jira_key}%22">{jira_key}</a>]</i>\n'
            )

        for jira_key in duplicates:
            issue['comments'].append(
                {"body": _comment_body(jira_key, 'duplicates')})

        for jira_key in is_duplicated_by:
            issue['comments'].append(
                {"body": _comment_body(jira_key, 'is_duplicated_by')})

        for jira_key in relates_to:
            issue['comments'].append(
                {"body": _comment_body(jira_key, 'relates_to')})

        for jira_key in depends_on:
            issue['comments'].append(
                {"body": _comment_body(jira_key, 'depends_on')})

        for jira_key in blocks:
            issue['comments'].append(
                {"body": _comment_body(jira_key, 'blocks')})

        if epic_key:
            issue['comments'].append(
                {"body": _comment_body(epic_key, 'epic')})

        del issue['duplicates']
        del issue['is-duplicated-by']
        del issue['is-related-to']
        del issue['depends-on']
        del issue['blocks']
        try:
            del issue['epic-link']
        except KeyError:
            pass

    def _replace_jira_with_github_id(self, text):
        result = text
        # for pattern, replacement in self.jira_issue_replace_patterns.items():
        #     result = re.sub(pattern, Importer._PLACEHOLDER_PREFIX +
        #                     replacement + Importer._PLACEHOLDER_SUFFIX, result)
        return result

    # def post_process_comments(self):
    #     """
    #     Starts post-processing all issue comments.
    #     """
    #     comment_url = self.github_api_url + '/issues/comments'
    #     self._post_process_comments(comment_url)

    # def _post_process_comments(self, url):
    #     """
    #     Paginates through all issue comments and replaces the issue id placeholders with the correct issue ids.
    #     """
    #     print("listing comments using " + url)
    #     response = requests.get(url, headers=self.headers,
    #         timeout=Importer._DEFAULT_TIME_OUT)
    #     if response.status_code != 200:
    #         raise RuntimeError(
    #             "Failed to list all comments due to unexpected HTTP status code: {}".format(
    #                 response.status_code)
    #         )

    #     comments = response.json()
    #     for comment in comments:
    #         print("handling comment " + comment['url'])
    #         body = comment['body']
    #         if Importer._PLACEHOLDER_PREFIX in body:
    #             newbody = self._replace_github_id_placeholder(body)
    #             self._patch_comment(comment['url'], newbody)
    #     try:
    #         next_comments = response.links["next"]
    #         if next_comments:
    #             next_url = next_comments['url']
    #             self._post_process_comments(next_url)
    #     except KeyError:
    #         print('no more pages for comments: ')
    #         for key, value in response.links.items():
    #             print(key)
    #             print(value)

    def _replace_github_id_placeholder(self, text):
        result = text
        # pattern = Importer._PLACEHOLDER_PREFIX + Importer._GITHUB_ISSUE_PREFIX + \
        #     r'(\d+)' + Importer._PLACEHOLDER_SUFFIX
        # result = re.sub(pattern, Importer._GITHUB_ISSUE_PREFIX + r'\1', result)
        # pattern = Importer._PLACEHOLDER_PREFIX + \
        #     r'(\d+)' + Importer._PLACEHOLDER_SUFFIX
        # result = re.sub(pattern, r'\1', result)
        return result

    # def _patch_comment(self, url, body):
    #     """
    #     Patches a single comment body of a Github issue.
    #     """
    #     print("patching comment " + url)
    #     # print("new body:" + body)
    #     patch_data = {'body': body}
    #     # print(patch_data)
    #     response = requests.patch(url, json=patch_data, headers=self.headers,
    #         timeout=Importer._DEFAULT_TIME_OUT)
    #     if response.status_code != 200:
    #         raise RuntimeError(
    #             "Failed to patch comment {} due to unexpected HTTP status code: {} ; text: {}".format(
    #                 url, response.status_code, response.text)
    #         )
