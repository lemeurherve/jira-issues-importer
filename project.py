import os
from collections import defaultdict
from html.entities import name2codepoint
from dateutil.parser import parse
import re
import requests
import time

from urllib.parse import quote

from utils import fetch_labels_mapping, fetch_allowed_labels, fetch_hosted_mappings, fetch_remote_links, convert_label, proper_label_str

from version import __version__

class Project:

    def __init__(self, config):
        self.config = config
        self.version = config.version
        self.name = config.name
        self.current_datetime = config.current_datetime
        self.doneStatusCategoryId = config.jira_done_id
        self.jiraBaseUrl = config.jira_base_url
        self._project = {
            'Milestones': defaultdict(int),
            'Components': defaultdict(int),
            'Labels': defaultdict(int),
            'Types': defaultdict(int),
            'Issues': []
        }

        self.labels_mapping = fetch_labels_mapping()
        self.approved_labels = fetch_allowed_labels()
        self.remote_links = fetch_remote_links()

        self.hosted_artifact_base = None
        if config.hosted_artifact_org_repo:
            self.hosted_artifact_base = f'https://raw.githubusercontent.com/{config.hosted_artifact_org_repo}/refs/heads/main'

        # Must be the same as the one in the hosted_artifact_org_repo
        self.mapping_foldername = 'mappings'

        # Keeping those filenames here so we can complete them during the import
        self.jira_fixed_username_filename = 'jira_fixed_usernames.txt'
        self.jira_username_avatar_mapping_filename = 'jira_username_avatar_mapping.txt'
        self.jira_attachments_filename = 'jira_attachments_repo_id_filename.txt'

        # Fields that utils will populate
        self.jira_fixed_usernames = {}
        self.jira_user_avatars = {}
        self.jira_attachments = {}

    def load_mappings(self):
        """
        Delegate the fetching logic to utils.
        """
        return fetch_hosted_mappings(self)

    def get_milestones(self):
        return self._project['Milestones']

    def get_components(self):
        return self._project['Components']

    def get_issues(self):
        return self._project['Issues']

    def get_types(self):
        return self._project['Types']

    def get_all_labels(self):
        merge = self._project['Components'].copy()
        merge.update(self._project['Labels'])
        merge.update(self._project['Types'])
        merge.update({'imported-jira-issue': 0})
        return merge

    def get_labels(self):
        merge = self._project['Labels'].copy()
        merge.update({'imported-jira-issue': 0})
        return merge

    def add_item(self, item):
        itemProject = self._projectFor(item)
        if itemProject != self.name:
            print('Skipping item ' + item.key.text + ' for project ' +
                  itemProject + ' current project: ' + self.name)
            return

        self._append_item_to_project(item)

        self._add_milestone(item)

        self._add_labels(item)

        self._add_subtasks(item)

        self._add_parenttask(item)

        self._add_comments(item)

        self._add_relationships(item)

    def prettify(self):
        def hist(h):
            for key in h.keys():
                print(('%30s (%5d): ' + h[key] * '#') % (key, h[key]))
            print

        print(self.name + ':\n  Milestones:')
        hist(self._project['Milestones'])
        print('  Types:')
        hist(self._project['Types'])
        print('  Components:')
        hist(self._project['Components'])
        print('  Labels:')
        hist(self._project['Labels'])
        print
        print('Total Issues to Import: %d' % len(self._project['Issues']))

    def _projectFor(self, item):
        try:
            result = item.project.get('key')
        except AttributeError:
            result = item.key.text.split('-')[0]
        return result

    def _append_item_to_project(self, item):
        # todo assignee
        closed = str(item.statusCategory.get('id')) == self.doneStatusCategoryId
        closed_at = ''
        if closed:
            try:
                closed_at = self._convert_to_iso(item.resolved.text)
            except AttributeError:
                pass

        # retrieve jira components and labels as github labels (add 'imported-jira-issue' label by default)
        labels = ['imported-jira-issue']
        print(item)
        for component in item.component:
            if os.getenv('JIRA_MIGRATION_INCLUDE_COMPONENT_IN_LABELS', 'true') == 'true':
                labels.append('component:' + proper_label_str(component.text[:40]))

        labels.append(self._jira_type_mapping(item.type.text.lower()))

        for label in item.labels.findall('label'):
            converted_label = convert_label(proper_label_str(label.text), self.labels_mapping, self.approved_labels)
            if converted_label is not None:
                labels.append(converted_label[:50])

        labels = list(filter(None, set(labels))) # Unique labels, filter out None

        body = self._clean_html(item.description.text)

        ## imported issue details block
        # metadata: original author & link
        reporter_fullname = item.reporter.text
        reporter_username = self._proper_jirauser_username(item.reporter.get('username'))
        reporter = self._username_and_avatar(reporter_username)
        issue_url = item.link.text
        issue_title_without_key = item.title.text[item.title.text.index("]") + 2:len(item.title.text)]
        body += f'\n\n---\n<details><summary><i>Originally reported by {reporter}, imported from: <a class="original-jira-link" href="{issue_url}" target="_blank">{issue_title_without_key}</a></i></summary>'
        body += '\n<i><ul>'

        # metadata: assignee
        if item.assignee != 'Unassigned':
            assignee_fullname = item.assignee.text
            assignee_username = self._proper_jirauser_username(item.assignee.get('username'))
            assignee = self._username_and_avatar(assignee_username)
            body += '\n<li><b>assignee</b>: ' + assignee
        else:
            assignee_username = ''

        # metadata: status
        try:
            body += '\n<li><b>status</b>: ' + item.status
        except AttributeError:
            pass

        # metadata: priority
        try:
            priority_txt = item.priority.text
            body += '\n<li><b>priority</b>: ' + priority_txt
            labels.append('priority:' + proper_label_str(priority_txt))
        except AttributeError:
            pass

        # metadata: components
        components_txt = ''
        for component in item.component:
            components_txt += ', ' + component.text if components_txt else component.text
        if components_txt:
            body += '\n<li><b>component(s)</b>: ' + components_txt

        # metadata: labels
        labels_txt = ''
        for label in item.labels.findall('label'):
            labels_txt += ', ' + label.text if labels_txt else label.text
        if labels_txt:
            body += '\n<li><b>label(s)</b>: ' + labels_txt

        # metadata: resolution
        try:
            resolution_txt = item.resolution.text
            body += '\n<li><b>resolution</b>: ' + resolution_txt
            labels.append('resolution:' + proper_label_str(resolution_txt))
        except AttributeError:
            pass

        # metadata: resolved
        try:
            body += '\n<li><b>resolved</b>: ' + self._convert_to_iso(item.resolved.text)
        except AttributeError:
            pass
        body += '\n<li><b>votes</b>: ' + str(item.votes)
        body += '\n<li><b>watchers</b>: ' + str(item.watches)
        body += '\n<li><b>imported</b>: ' + self.current_datetime
        body += '\n</ul></i>'
        if item.description.text is not None:
            body += '\n<details><summary>Raw content of original issue</summary>\n\n<pre>\n' + item.description.text.replace('<br/>', '') + '</pre>\n</details>'

        ## End of issue details block
        body += '\n</details>'

        # metadata: environment
        try:
            environment_value = item.environment.text.strip()
            if environment_value:
                environment_txt = '<ul><li><i>environment</i>: <code>' + environment_value + '</code></li></ul>'
                lines = environment_value.splitlines()
                # Remove empty lines
                lines = [line for line in lines if line.replace('<br/>', '').strip() != '']
                if len(lines) > 1:
                    environment_txt = '<details><summary><i>environment</i></summary>\n\n```\n' + '\n'.join(lines) + '\n```\n</details>'
                body += '\n' + environment_txt
        except AttributeError:
            pass

        # metadata: attachments
        try:
            attachments = []
            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
            for attachment in item.attachments.attachment:
                attachment_id = attachment.get('id')
                attachment_name = attachment.get('name')
                attachment_extension = os.path.splitext(attachment_name)[1].lower()

                attachment_url = f'{self.jiraBaseUrl}/secure/attachment/{attachment_id}/{quote(attachment_name)}'
                if attachment_id in self.jira_attachments:
                    attachment_url = 'https://raw.githubusercontent.com/' + quote(self.jira_attachments[attachment_id])

                attachment_txt = f'[{attachment_name}]({attachment_url})'
                if attachment_extension in image_extensions:
                    attachment_txt = attachment_txt + '\n  > !' + attachment_txt

                attachments.append('\n- ' + attachment_txt)
            if len(attachments) > 0:
                summary = str(len(attachments)) + ' attachments' if len(attachments) > 1 else '1 attachment'
                body += '\n<details><summary><i>' + summary + '</i></summary>\n' + ''.join(attachments) + '\n</details>'
        except AttributeError:
            pass

        # References for better searching
        hidden_refs = '<!-- ### Imported Jira references for easier searching -->'
        hidden_refs += f'\n<!-- [jira_issue_key={item.key.text}] -->'
        # TODO: map Jira issue types <> GitHub issue types
        # add github_issue_type (for post-process)
        # then don't add jira-type:<type> labels
        issue_type = ' '.join(item.type.text.strip().split())
        hidden_refs += f'\n<!-- [jira_issue_type={issue_type}] -->'
        # epic
        if issue_type == 'Epic':
            hidden_refs += f'\n<!-- [jira_issue_is_epic_key={item.key.text}] -->'
        epic_key = self._find_epic_link_key(item)
        if epic_key:
            hidden_refs += f'\n<!-- [jira_relationships_epic_key={epic_key}] -->'
        # Putting both username and full name for reporter and assignee in case they differ
        hidden_refs += f'\n<!-- [reporter={reporter_username}] -->'
        if assignee_username:
            hidden_refs += f'\n<!-- [assignee={assignee_username}] -->'
        # Adding the reporter as "author" too in those references
        hidden_refs += f'\n<!-- [author={reporter_username}] -->'
        # components
        for component in item.component:
            hidden_refs += f'\n<!-- [jira_component={component.text}] -->'
        # labels
        for label in item.labels.findall('label'):
            hidden_refs += f'\n<!-- [jira_label={label.text}] -->'

        # Add version of the importer for future references
        hidden_refs += '\n<!-- [jira_issues_importer_version=' + self.version + '] -->'

        # Put hidden refs on top of body
        body = hidden_refs + '\n\n' + body

        # Apply Jira URL rewriting to the entire body (including metadata sections)
        body = self._replace_jira_urls_with_redirection_service(body)

        # _ keys are only there for gathering import data
        self._project['Issues'].append({'title': item.title.text,
                                        'key': item.key.text,
                                        'body': body,
                                        'created_at': self._convert_to_iso(item.created.text),
                                        'closed_at': closed_at,
                                        'updated_at': self._convert_to_iso(item.updated.text),
                                        'closed': closed,
                                        'labels': labels,
                                        'comments': [],
                                        'duplicates': [],
                                        'is-duplicated-by': [],
                                        'is-related-to': [],
                                        'depends-on': [],
                                        'blocks': [],
                                        '_watchers_count': str(item.watches),
                                        '_votes_count': str(item.votes),
                                        })
        if not self._project['Issues'][-1]['closed_at']:
            del self._project['Issues'][-1]['closed_at']

    def _jira_type_mapping(self, issue_type):
        if issue_type == 'bug':
            return 'bug'
        if issue_type == 'improvement':
            return 'enhancement'
        if issue_type == 'new feature':
            return 'enhancement'
        if issue_type == 'task':
            return 'jira-type:task'
        if issue_type == 'story':
            return 'jira-type:story'
        if issue_type == 'patch':
            return 'jira-type:patch'
        if issue_type == 'epic':
            return 'jira-type:epic'

    def _convert_to_iso(self, timestamp):
        dt = parse(timestamp)
        return dt.isoformat()

    def _add_milestone(self, item):
        try:
            self._project['Milestones'][item.fixVersion.text] += 1
            # this prop will be deleted later:
            self._project['Issues'][-1]['milestone_name'] = item.fixVersion.text.trim()
        except AttributeError:
            pass

    def _add_labels(self, item):
        try:
            self._project['Components'][item.component.text] += 1
            tmp_l = item.component.text.trim()
            if tmp_l == 'Bug':
                tmp_l = 'bug'

            self._project['Issues'][-1]['labels'].append(tmp_l)
        except AttributeError:
            pass
        
        try:
            for label in item.labels.label:
                self._project['Labels'][label.text] += 1
                tmp_l = label.text.trim()
                if tmp_l == 'Bug':
                    tmp_l = 'bug'

                self._project['Issues'][-1]['labels'].append(tmp_l)
        except AttributeError:
            pass

        try:
            self._project['Types'][item.type.text] += 1
            tmp_l = item.type.text.trim()
            if tmp_l == 'Bug':
                tmp_l = 'bug'

            self._project['Issues'][-1]['labels'].append(tmp_l)
        except AttributeError:
            pass

    def _add_subtasks(self, item):
        try:
            subtaskList = ''
            for subtask in item.subtasks.subtask:
                subtaskList = subtaskList + '- ' + subtask + '\n'
            if subtaskList != '':
                print('-> subtaskList: ' + subtaskList)
                self._project['Issues'][-1]['comments'].append(
                    {"created_at": self._convert_to_iso(item.created.text),
                     "body": 'Subtasks:\n\n' + subtaskList})
        except AttributeError:
            pass

    def _add_parenttask(self, item):
        try:
            parentTask = item.parent.text
            if parentTask != '':
                print('-> parentTask: ' + parentTask)
                self._project['Issues'][-1]['comments'].append(
                    {"created_at": self._convert_to_iso(item.created.text),
                     "body": 'Subtask of parent task ' + parentTask})
        except AttributeError:
            pass

    def _rewrite_attachment_urls(self, html, attachment_map):
        if not self.hosted_artifact_base:
            return html  # nothing to rewrite

        # Pattern to match attachment or thumbnail URLs
        pattern = re.compile(
            rf'{self.jiraBaseUrl}/secure/(?:attachment|thumbnail)/(\d+)/(?:[^"]+)',
            re.IGNORECASE
        )

        def repl(m):
            attachment_id = m.group(1)
            filename = attachment_map.get(attachment_id)
            if not filename:
                return m.group(0)
            if attachment_id not in self.jira_attachments:
                return m.group(0)
            return 'https://raw.githubusercontent.com/' + quote(self.jira_attachments[attachment_id])

        return pattern.sub(repl, html)

    def _add_comments(self, item):

        self._add_remote_links_comment(item)

        attachment_map = {}
        try:
            for att in item.attachments.attachment:
                attachment_map[att.get('id')] = att.get('name')
        except AttributeError:
            pass

        try:
            for comment in item.comments.comment:
                comment_id = comment.get('id')
                comment_username = self._proper_jirauser_username(comment.get('author'))
                comment_author = self._username_and_avatar(comment_username, 'for_comment')
                a_comment_link = f'<a class="no-jira-link-rewrite" href="{item.link.text}?focusedId={comment_id}&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-{comment_id}">'
                a_comment_link_original = f'<a class="original-jira-link" href="{item.link.text}?focusedId={comment_id}&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-{comment_id}">'
                comment_raw_details = ''
                comment_text = ''
                if comment.text is not None:
                    raw_html = comment.text
                    comment_text = self._clean_html(self._rewrite_attachment_urls(raw_html, attachment_map))
                    comment_raw = raw_html.replace('<br/>', '')
                    if len(comment_raw_details) < 65000:
                        comment_raw_details = (
                            f'<li><details><summary><i>Raw content of original comment:</i></summary>\n\n'
                            f'<pre>\n'
                            f'{comment_raw}\n'
                            f'</pre>\n'
                            f'</details>\n'
                        )
                comment_body = (
                    f'<details><summary><i>{comment_author}:</i></summary>\n\n'
                    f'<ul>\n'
                    f'<li><i>{a_comment_link}Comment link</a></i>\n'
                    f'<li><i>Original {a_comment_link_original}comment link</a> (no redirect)</i>\n'
                    f'{comment_raw_details}\n'
                    f'</ul>\n'
                    f'</details>\n\n'
                    f'{comment_text}'
                )

                # References for better searching
                comment_body = (
                    f'<!-- ### Imported Jira references for easier searching -->\n'
                    f'<!-- [jira_issue_key={item.key.text}] -->\n'
                    f'<!-- [jira_comment_id={comment_id}] -->\n'
                    f'<!-- [comment_author={comment_username}] -->\n'
                ) + comment_body

                # Apply Jira URL rewriting to the entire comment body (including metadata sections)
                comment_body = self._replace_jira_urls_with_redirection_service(comment_body)

                self._project['Issues'][-1]['comments'].append({
                    "created_at": self._convert_to_iso(comment.get('created')),
                    "body": comment_body
                })
        except AttributeError:
            pass

    def _add_remote_links_comment(self, item):
        issue_key = item.key.text
        if issue_key in self.remote_links:
            links = self.remote_links[issue_key]
            plural = 's' if len(links) != 1 else ''

            comment_body = (
                f'<!-- ### Imported Jira references for easier searching -->\n'
                f'<!-- [synthetic_comment=remote_links] -->\n'
                f'- _Remote link{plural} associated with this issue:_\n\n'
            )
            for rl in links:
                comment_body += f'\n  - {rl}'

            self._project["Issues"][-1]["comments"].append({
                "created_at": self._convert_to_iso(item.created.text),
                "body": comment_body,
            })

    def _add_relationships(self, item):
        try:
            for issuelinktype in item.issuelinks.issuelinktype:
                for outwardlink in issuelinktype.outwardlinks:
                    for issuelink in outwardlink.issuelink:
                        for issuekey in issuelink.issuekey:
                            tmp_outward = outwardlink.get("description").replace(' ', '-')
                            if tmp_outward in self._project['Issues'][-1]:
                                self._project['Issues'][-1][tmp_outward].append(issuekey.text)
        except AttributeError:
            pass
        except KeyError:
            print('1. KeyError at ' + item.key.text)
        try:
            for issuelinktype in item.issuelinks.issuelinktype:
                for inwardlink in issuelinktype.inwardlinks:
                    for issuelink in inwardlink.issuelink:
                        for issuekey in issuelink.issuekey:
                            tmp_inward = inwardlink.get("description").replace(' ', '-')
                            if tmp_inward in self._project['Issues'][-1]:
                                self._project['Issues'][-1][tmp_inward].append(issuekey.text)
        except AttributeError:
            pass
        except KeyError:
            print('2. KeyError at ' + item.key.text)

        self._project['Issues'][-1]['epic-link'] = self._find_epic_link_key(item)

    def _find_epic_link_key(self, item):
        for customfield in item.customfields.findall('customfield'):
            if customfield.get('key') == 'com.pyxis.greenhopper.jira:gh-epic-link':
                return customfield.customfieldvalues.customfieldvalue
        return None

    def _htmlentitydecode(self, s):
        if s is None:
            return ''
        s = s.replace(' ' * 8, '')
        return re.sub('&(%s);' % '|'.join(name2codepoint),
                      lambda m: chr(name2codepoint[m.group(1)]), s)

    def _replace_jira_urls_with_redirection_service(self, s):
        """
        Replace Jira browse URLs with redirection service URLs if configured.
        Preserves query strings from the original URLs.
        Excludes links marked with 'original-jira-link' class.

        Example: https://issues.jenkins.io/browse/INFRA-123?focusedId=456
                 -> https://issue-redirect.jenkins.io/issue/123?focusedId=456
        """
        if s is None or not self.config.redirection_service:
            return s if s is not None else ''

        # Pattern to match any Jira browse URL (with or without https://)
        # Uses negative lookbehind to exclude 'original-jira-link' class links
        # Multiple lookbehinds handle cases with/without protocol in the href attribute
        # Remove protocol from jiraBaseUrl since we'll add an optional one
        jira_base_without_protocol = self.jiraBaseUrl.replace('https://', '').replace('http://', '')
        escaped_jira_base_url = jira_base_without_protocol.replace('.', r'\.')
        pattern = (
            rf'(?<!<a class="original-jira-link" href=")'
            rf'(?<!<a class="original-jira-link" href="https://)'
            rf'(?<!<a class="original-jira-link" href="http://)'
            # TODO: use escape
            rf'(?:https?://)?{escaped_jira_base_url}/browse/{self.name}-(\d+)(\?[^\s<>"]*)?'
        )

        # Replace with redirection service URL + issue number + query string (if present)
        issue_number_and_query = r'\1\2'
        # TODO: use project name when redirection service allows it to allow multiple projects (ex: JENKINS, INFRA)
        # replacement = f'{self.config.redirection_service}/{self.name}/{issue_number_and_query}'
        replacement = f'{self.config.redirection_service}/issue/{issue_number_and_query}'

        return re.sub(pattern, replacement, s)

    def _clean_html(self, s):
        if s is None:
            return ''
        s = self._htmlentitydecode(s)
        # Cleanup of Jira specific markup rendered HTML with non-greedy multiline regexps
        # Handle {code}: need special handling as Jira insert HTML spans for {code} block content highlighting
        s = re.sub(r'<div class="code panel" style="border-width: 1px;"><div class="codeContent panelContent">\n<pre class="code-[^"]*">(.*?)</pre>\n</div></div>', r'\n<pre>\n\1</pre>', s, flags=re.DOTALL)
        # Handle {noformat}
        s = re.sub(r'<div class="preformatted panel" style="border-width: 1px;"><div class="preformattedContent panelContent">\n<pre>(.*?)</pre>\n</div></div>', r'\n\n```\n\1\n```', s, flags=re.DOTALL)
        # Handle {panel:title}: processed first to avoid matching by the no-title pattern
        s = re.sub(r'<div class="panel" style="border-width: 1px;"><div class="panelHeader" style="border-bottom-width: 1px;"><b>(.*?)</b></div><div class="panelContent">\s*(.*?)\s*</div></div>', r'\n\n<table><tr><td><b>\1</b></td></tr><tr><td>\2</td></tr></table>\n', s, flags=re.DOTALL)
        # Handle {panel}
        s = re.sub(r'<div class="panel" style="border-width: 1px;"><div class="panelContent">\s*(.*?)\s*</div></div>', r'\n\n<table><tr><td>\1</td></tr></table>\n', s, flags=re.DOTALL)

        # Escape @mentions to prevent unwanted mentions in GitHub
        s = re.sub(r'@([A-Za-z0-9._-]+)', '@\u200B\\1', s)

        return s

    def _proper_jirauser_username(self, name):
        if name.startswith('JIRAUSER') and name in self.jira_fixed_usernames:
            return self.jira_fixed_usernames[name]
        return name

    # In case JIRAUSER* proper usernames are not found
    def _username_and_avatar(self, name, for_comment = ''):
        username = self._proper_jirauser_username(name)
        avatar = ''
        # Retrieve avatars only if JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO is set
        if self.hosted_artifact_base:
            if username in self.jira_user_avatars:
                avatar_path = self.hosted_artifact_base + '/' + self.jira_user_avatars[username]
                avatar = f'<img align="left" width="20" src="{avatar_path}" title="{username}\'s avatar" /> '
        # No profile page for JIRAUSER* accounts
        if username.startswith('JIRAUSER') or for_comment:
            profile = username
        else:
            profile = f'<a href="{self.jiraBaseUrl}/secure/ViewProfile.jspa?name={name}">{username}</a>'
        return f'{avatar}{profile}'
