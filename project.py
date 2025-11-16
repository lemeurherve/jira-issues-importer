import os
from collections import defaultdict
from html.entities import name2codepoint
from dateutil.parser import parse
from datetime import datetime
import re
import requests
from urllib.parse import quote

from utils import fetch_labels_mapping, fetch_allowed_labels, fetch_jira_fixed_usernames, fetch_jira_user_avatars, convert_label, proper_label_str


class Project:

    def __init__(self, name, doneStatusCategoryId, jiraBaseUrl):
        self.name = name
        self.doneStatusCategoryId = doneStatusCategoryId
        self.jiraBaseUrl = jiraBaseUrl
        self._project = {'Milestones': defaultdict(int), 'Components': defaultdict(
            int), 'Labels': defaultdict(int), 'Types': defaultdict(int), 'Issues': []}

        self.labels_mapping = fetch_labels_mapping()
        self.approved_labels = fetch_allowed_labels()

        self.jira_fixed_username_file = 'jira_fixed_usernames.txt'
        self.jira_username_avatar_mapping_file = 'jira_username_avatar_mapping.txt'
        # "org/repo" hosting artifacts like avatars, attachments and username mappings
        # If not set, will use local files, and won't add avatar in issues or comments
        # Example of such repo: https://github.com/lemeurherve/artifacts-from-jira-issues-example
        if os.getenv('JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO'):
            self.hosted_artifact_base = 'https://raw.githubusercontent.com/' + os.getenv('JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO') + '/refs/heads/main'

            # Download mappings from hosted artifacts repo for further inspection post import
            print('Downloading mappings from ' + os.getenv('JIRA_MIGRATION_HOSTED_ARTIFACT_ORG_REPO') + ' if they don\'t already exist')
            if not os.path.exists(self.jira_fixed_username_file):
                response = requests.get(self.hosted_artifact_base + '/mappings/' + self.jira_fixed_username_file)
                open(self.jira_fixed_username_file, 'w').write(response.text)
                print(self.jira_fixed_username_file + ' downloaded')
            if not os.path.exists(self.jira_username_avatar_mapping_file):
                response = requests.get(self.hosted_artifact_base + '/mappings/' + self.jira_username_avatar_mapping_file)
                open(self.jira_username_avatar_mapping_file, 'w').write(response.text)
                print(self.jira_username_avatar_mapping_file + ' downloaded')

            # As avatars can only be displayed if they're hosted, load its mapping only in that case
            self.jira_user_avatars = fetch_jira_user_avatars(self.jira_username_avatar_mapping_file)

        # load proper usernames mapping from file (from local file, eventually downloaded above)
        self.jira_fixed_usernames = fetch_jira_fixed_usernames(self.jira_fixed_username_file)

        self.version = '1.0.0'

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
        for component in item.component:
            if os.getenv('JIRA_MIGRATION_INCLUDE_COMPONENT_IN_LABELS', 'true') == 'true':
                labels.append('component:' + proper_label_str(component.text[:40]))

        labels.append(self._jira_type_mapping(item.type.text.lower()))

        for label in item.labels.findall('label'):
            converted_label = convert_label(proper_label_str(label.text), self.labels_mapping, self.approved_labels)
            if converted_label is not None:
                labels.append(converted_label[:50])

        body = self._clean_html(item.description.text)

        ## imported issue details block
        # metadata: original author & link
        reporter_fullname = item.reporter.text
        reporter_username = self._proper_jirauser_username(item.reporter.get('username'))
        reporter = self._username_and_avatar(reporter_username)
        issue_url = item.link.text
        issue_title_without_key = item.title.text[item.title.text.index("]") + 2:len(item.title.text)]
        body += '\n\n---\n<details><summary><i>Originally reported by ' + reporter + ', imported from: <a href="' + issue_url + '" target="_blank">' + issue_title_without_key + '</a></i></summary>'
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
        body += '\n<li><b>imported</b>: ' + datetime.today().strftime('%Y-%m-%d')
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
                attachment_name = attachment.get('name')
                attachment_extension = os.path.splitext(attachment_name)[1].lower()
                attachment_txt = '[{0}]({1}/secure/attachment/{2}/{3})'.format(
                    attachment_name,
                    self.jiraBaseUrl,
                    attachment.get('id'),
                    quote(attachment_name),
                )
                if attachment_extension in image_extensions:
                    attachment_txt = attachment_txt + '\n  > !' + attachment_txt

                attachments.append('\n- ' + attachment_txt)
            if len(attachments) > 0:
                summary = str(len(attachments)) + ' attachments' if len(attachments) > 1 else '1 attachment'
                body += '\n<details><summary><i>' + summary + '</i></summary>\n' + ''.join(attachments) + '\n</details>'
        except AttributeError:
            pass

        # References for better searching
        body += '\n\n<!-- ### Imported Jira references for easier searching -->'
        body += f'\n<!-- [jira_issue_key={item.key.text}] -->'
        # Putting both username and full name for reporter and assignee in case they differ
        body += f'\n<!-- [reporter={reporter_username}] -->'
        if assignee_username:
            body += f'\n<!-- [assignee={assignee_username}] -->'
        # Adding the reporter as "author" too in those references
        body += f'\n<!-- [author={reporter_username}] -->'
        # components
        for component in item.component:
            body += f'\n<!-- [jira_component={component.text}] -->'
        # labels
        for label in item.labels.findall('label'):
            body += f'\n<!-- [jira_label={label.text}] -->'

        # Add version of the importer for future references
        body += '\n<!-- [importer_version=' + self.version + '] -->'

        unique_labels = list(set(labels))

        self._project['Issues'].append({'title': item.title.text,
                                        'key': item.key.text,
                                        'body': body,
                                        'created_at': self._convert_to_iso(item.created.text),
                                        'closed_at': closed_at,
                                        'updated_at': self._convert_to_iso(item.updated.text),
                                        'closed': closed,
                                        'labels': unique_labels,
                                        'comments': [],
                                        'duplicates': [],
                                        'is-duplicated-by': [],
                                        'is-related-to': [],
                                        'depends-on': [],
                                        'blocks': []
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

    def _add_comments(self, item):
        try:
            for comment in item.comments.comment:
                comment_id = comment.get('id')
                comment_author = self._username_and_avatar(comment.get('author'), 'for_comment')
                comment_link = item.link.text + '?focusedId=' + comment_id + '&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-' + comment_id
                if comment.text is not None:
                    comment_text = self._clean_html(comment.text)
                    comment_raw = comment.text.replace('<br/>', '')
                    comment_raw_details = (
                        f'\n<details><summary><sub><i>Raw content of original comment:</i></sub></summary>\n'
                        f'\n<pre>'
                        f'\n{comment_raw}'
                        f'\n</pre>'
                        f'\n</details>'
                    )
                else:
                    comment_raw = ''
                    comment_raw_details = ''
                    comment_text = ''

                if len(comment_raw_details) > 65000:
                    comment_body = '<sup><i>' + comment_author + '\'s <a href="' + comment_link + '">comment</a>:</i></sup>\n' + comment_text
                else:
                    comment_body = (
                        f'\n<details><summary><i>{comment_author}\'s <a href="{comment_link}">comment</a>:</i></summary>\n'
                        f'\n{comment_raw_details}\n'
                        f'\n</details>'
                        f'\n{comment_text}'
                    )

                # References for better searching
                comment_body += (
                    f'\n\n<!-- ### Imported Jira references for easier searching -->'
                    f'\n<!-- [jira_issue_key={item.key.text}] -->'
                    f'\n<!-- [jira_comment_id={comment_id}] -->'
                    f'\n<!-- [comment_author={comment_author}] -->'
                )

                self._project['Issues'][-1]['comments'].append(
                    {"created_at": self._convert_to_iso(comment.get('created')),
                     "body": comment_body
                     })
        except AttributeError:
            pass

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

        for customfield in item.customfields.findall('customfield'):
            if customfield.get('key') == 'com.pyxis.greenhopper.jira:gh-epic-link':
                epic_key = customfield.customfieldvalues.customfieldvalue
                self._project['Issues'][-1]['epic-link'] = epic_key

    def _htmlentitydecode(self, s):
        if s is None:
            return ''
        s = s.replace(' ' * 8, '')
        return re.sub('&(%s);' % '|'.join(name2codepoint),
                      lambda m: chr(name2codepoint[m.group(1)]), s)

    def _clean_html(self, s):
        if s is None:
            return ''
        s = self._htmlentitydecode(s)
        # Cleanup of Jira specific markup rendered HTML with non-greedy multiline regexps
        # Handle {code}: need special handling as Jira insert HTML spans for {code} block content highlighting
        s = re.sub(r'<div class="code panel" style="border-width: 1px;"><div class="codeContent panelContent">\n<pre class="code-[^"]*">(.*?)</pre>\n</div></div>', r'\n<pre>\n\1</pre>', s, flags=re.DOTALL)
        # Handle {noformat}
        s = re.sub(r'<div class="preformatted panel" style="border-width: 1px;"><div class="preformattedContent panelContent">\n<pre>(.*?)</pre>\n</div></div>', r'\n\n```\n\1```', s, flags=re.DOTALL)
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
