import os
import requests
import time

from utils import fetch_labels_mapping, fetch_allowed_labels, convert_label


class Importer:
    _GITHUB_ISSUE_PREFIX = "INFRA-"
    _PLACEHOLDER_PREFIX = "@PSTART"
    _PLACEHOLDER_SUFFIX = "@PEND"
    _DEFAULT_TIME_OUT = 120.0

    def __init__(self, options, project):
        self.options = options
        self.project = project
        self.github_url = 'https://api.github.com/repos/%s/%s' % (
            self.options.account, self.options.repo)
        self.jira_issue_replace_patterns = {
            'https://issues.jenkins.io/browse/%s%s' % (self.project.name, r'-(\d+)'): r'\1',
            self.project.name + r'-(\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1',
            r'Issue (\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1'}
        self.headers = {
            'Accept': 'application/vnd.github.golden-comet-preview+json',
            'Authorization': f'token {options.accesstoken}'
        }

        self.labels_mapping = fetch_labels_mapping()
        self.approved_labels = fetch_allowed_labels()

    def import_milestones(self):
        """
        Imports the gathered project milestones into GitHub and remembers the created milestone ids
        """
        milestone_url = self.github_url + '/milestones'
        print('Importing milestones...', milestone_url)
        print

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
            r = requests.post(milestone_url, json=data, headers=self.headers,
                timeout=Importer._DEFAULT_TIME_OUT)

            # overwrite histogram data with the actual milestone id now
            if r.status_code == 201:
                content = r.json()
                self.project.get_milestones()[mkey] = content['number']
                print(mkey)


    def import_labels(self, colour_selector):
        """
        Imports the gathered project components and labels as labels into GitHub 
        """
        label_url = self.github_url + '/labels'
        print('Importing labels...', label_url)
        print()

        for lkey in self.project.get_all_labels().keys():

            prefixed_lkey = lkey.lower()
            # prefix component
            if os.getenv('JIRA_MIGRATION_INCLUDE_COMPONENT_IN_LABELS', 'true') == 'true':
                if lkey in self.project.get_components().keys():
                    prefixed_lkey = 'jira-component:' + prefixed_lkey

            prefixed_lkey = convert_label(prefixed_lkey, self.labels_mapping, self.approved_labels)
            if prefixed_lkey is None:
                continue

            data = {'name': prefixed_lkey,
                    'color': colour_selector.get_colour(lkey)}
            r = requests.post(label_url, json=data, headers=self.headers, timeout=Importer._DEFAULT_TIME_OUT)
            if r.status_code == 201:
                print(lkey + '->' + prefixed_lkey)
            else:
                print('Failure importing label ' + prefixed_lkey,
                      r.status_code, r.content, r.headers)

    def import_issues(self, start_from_count):
        """
        Starts the issue import into GitHub:
        First the milestone id is captured for the issue.
        Then JIRA issue relationships are converted into comments.
        After that, the comments are taken out of the issue and 
        references to JIRA issues in comments are replaced with a placeholder    
        """
        print('Importing issues...')

        count = 0

        for issue in self.project.get_issues():
            if start_from_count > count:
                count += 1
                continue

            print("Index = ", count)

            if 'milestone_name' in issue:
                issue['milestone'] = self.project.get_milestones()[
                    issue['milestone_name']]
                del issue['milestone_name']

            self.convert_relationships_to_comments(issue)

            issue_comments = issue['comments']
            del issue['comments']
            comments = []
            for comment in issue_comments:
                comments.append(
                    dict((k, self._replace_jira_with_github_id(v)) for k, v in comment.items()))

            self.import_issue_with_comments(issue, comments)
            count += 1

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

        response = self.upload_github_issue(issue, comments)
        status_url = response.json()['url']
        gh_issue_url = self.wait_for_issue_creation(status_url).json()['issue_url']
        gh_issue_id = int(gh_issue_url.split('/')[-1])
        issue['githubid'] = gh_issue_id
        issue['key'] = jira_key

        jira_gh = f"{jira_key}:{gh_issue_id}\n"
        with open('jira-keys-to-github-id.txt', 'a') as f:
            f.write(jira_gh)

    def upload_github_issue(self, issue, comments):
        """
        Uploads a single issue to GitHub asynchronously with the Issue Import API.
        """
        issue_url = self.github_url + '/import/issues'
        issue_data = {'issue': issue, 'comments': comments}
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
                "Failed to POST issue: '{}' due to unexpected HTTP status code: {}\nerrors:\n{}"
                .format(issue['title'], response.status_code, response.json())
            )

    def wait_for_issue_creation(self, status_url):
        """
        Check the status of a GitHub issue import.
        If the status is 'pending', it sleeps, then rechecks until the status is
        either 'imported' or 'failed'.
        """
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
            epic_link = issue['epic-link']
        except (AttributeError, KeyError):
            epic_link = None

        for duplicate_item in duplicates:
            issue['comments'].append(
                {"body": f'<i>[Duplicates: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(duplicate_item) + '">' + self._replace_jira_with_github_id(duplicate_item) + '</a>]</i>'})

        for is_duplicated_by_item in is_duplicated_by:
            issue['comments'].append(
                {"body": f'<i>[Originally duplicated by: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(is_duplicated_by_item) + '">' + self._replace_jira_with_github_id(is_duplicated_by_item) + '</a>]</i>'})

        for relates_to_item in relates_to:
            issue['comments'].append(
                {"body": f'<i>[Originally related to: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(relates_to_item) + '">' + self._replace_jira_with_github_id(relates_to_item) + '</a>]</i>'})

        for depends_on_item in depends_on:
            issue['comments'].append(
                {"body": f'<i>[Originally depends on: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(depends_on_item) + '">' + self._replace_jira_with_github_id(depends_on_item) + '</a>]</i>'})

        for blocks_item in blocks:
            issue['comments'].append(
                {"body": f'<i>[Originally blocks: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(blocks_item) + '">' + self._replace_jira_with_github_id(blocks_item) + '</a>]</i>'})

        if epic_link:
            issue['comments'].append(
                {"body": f'<i>[Epic: <a href="https://github.com/{self.options.account}/{self.options.repo}/issues?q=in%3Atitle%20' + self._replace_jira_with_github_id(epic_link) + '%20label%3Aepic">' + self._replace_jira_with_github_id(epic_link) + '</a>]</i>'})

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
    #     comment_url = self.github_url + '/issues/comments'
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
