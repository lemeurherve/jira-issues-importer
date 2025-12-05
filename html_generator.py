#!/usr/bin/env python3
"""
HTML Generator for GitHub Issue Mock Interface
Converts dry-run JSON/MD output to HTML files that closely mimic GitHub's UI.
"""

import json
import os
from datetime import datetime
from html import escape
import re

try:
    import cmarkgfm
    CMARKGFM_AVAILABLE = True
except ImportError:
    CMARKGFM_AVAILABLE = False
    print("Warning: cmarkgfm not available. Install with: pip install cmarkgfm")
    print("Falling back to basic markdown rendering.")


class GitHubHTMLGenerator:
    """Generates HTML files that mimic GitHub's issue interface."""

    # GitHub-like color palette
    COLORS = {
        'bg_primary': '#ffffff',
        'bg_secondary': '#f6f8fa',
        'bg_tertiary': '#f3f4f6',
        'border': '#d0d7de',
        'border_muted': '#e5e7eb',
        'text_primary': '#24292f',
        'text_secondary': '#57606a',
        'text_muted': '#6e7681',
        'link': '#0969da',
        'link_hover': '#0550ae',
        'state_open_bg': '#1a7f37',
        'state_open_text': '#ffffff',
        'state_closed_bg': '#8250df',
        'state_closed_text': '#ffffff',
        'label_bg': '#ddf4ff',
        'label_border': '#54aeff',
        'label_text': '#0969da',
    }

    @staticmethod
    def _get_label_color(label_name):
        """Generate a consistent color for a label based on its name."""
        # Simple hash-based color generation
        hash_val = sum(ord(c) for c in label_name)
        colors = [
            ('#0969da', '#ddf4ff'),  # blue
            ('#1a7f37', '#dafbe1'),  # green
            ('#8250df', '#fbefff'),  # purple
            ('#cf222e', '#ffebe9'),  # red
            ('#bc4c00', '#fff1e5'),  # orange
            ('#6e7681', '#eaeef2'),  # gray
        ]
        idx = hash_val % len(colors)
        return colors[idx]

    @staticmethod
    def _format_date(date_str):
        """Format date string to GitHub-like format."""
        if not date_str or date_str == '-':
            return 'Unknown'
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%b %d, %Y')
        except:
            return date_str

    @staticmethod
    def _render_markdown_to_html(md_text):
        """Render content to HTML using GitHub Flavored Markdown.

        Handles both HTML and markdown input. Uses cmarkgfm (GitHub's cmark fork)
        for accurate GFM rendering including:
        - Fenced code blocks with syntax highlighting
        - Tables
        - Strikethrough
        - Autolinks
        - Task lists
        - And all other GFM features

        Content is returned without wrapping - wrapping with markdown-body class
        is done by the caller.
        """
        if not md_text:
            return '<p><em>No description provided</em></p>'

        # Check if content is already HTML (contains HTML tags that aren't markdown)
        # Be more conservative - only treat as HTML if it has block-level HTML
        has_block_html = bool(re.search(r'<(?:div|p|ul|ol|li|details|summary|pre|blockquote|h[1-6])[>\s]', md_text))

        if has_block_html:
            # Content is already HTML, return as-is
            return md_text

        # Use cmarkgfm for proper GitHub Flavored Markdown rendering
        if CMARKGFM_AVAILABLE:
            try:
                # Use GitHub Flavored Markdown rendering
                # This handles all GFM features: code blocks, tables, strikethrough, etc.
                html = cmarkgfm.github_flavored_markdown_to_html(md_text)
                return html
            except Exception as e:
                print(f"Warning: cmarkgfm rendering failed: {e}. Falling back to basic rendering.")
                # Fall through to basic rendering

        # Fallback: Basic markdown conversion (if cmarkgfm not available)
        html = escape(md_text)

        # Convert markdown links
        html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

        # Convert images
        html = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<img src="\2" alt="\1">', html)

        # Convert bold
        html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)

        # Convert italic
        html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)

        # Convert strikethrough
        html = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', html)

        # Convert code blocks
        html = re.sub(r'```([^`]+)```', r'<pre><code>\1</code></pre>', html)

        # Convert inline code
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # Convert paragraphs
        paragraphs = html.split('\n\n')
        html = ''.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs if p.strip())

        return html

    def generate_html(self, json_file, output_file=None):
        """Generate HTML file from JSON dry-run output."""
        # Read JSON data
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        issue = data.get('issue', {})
        comments = data.get('comments', [])

        # Extract issue metadata
        jira_key = os.path.basename(json_file).replace('.json', '')
        title = issue.get('title', 'Untitled')
        state = issue.get('state', 'open')
        labels = issue.get('labels', [])
        assignee = issue.get('assignee', None)
        milestone = issue.get('milestone', None)
        created_at = issue.get('created_at', '')
        closed_at = issue.get('closed_at', '')
        body = issue.get('body', '')

        # Generate HTML
        html = self._generate_issue_html(
            jira_key=jira_key,
            title=title,
            state=state,
            labels=labels,
            assignee=assignee,
            milestone=milestone,
            created_at=created_at,
            closed_at=closed_at,
            body=body,
            comments=comments
        )

        # Write to file
        if output_file is None:
            output_file = json_file.replace('.json', '.html')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_file

    def _generate_issue_html(self, jira_key, title, state, labels, assignee,
                            milestone, created_at, closed_at, body, comments):
        """Generate complete HTML for an issue."""
        c = self.COLORS

        # State badge
        state_class = 'open' if state == 'open' else 'closed'
        state_bg = c['state_open_bg'] if state == 'open' else c['state_closed_bg']
        state_text = c['state_open_text'] if state == 'open' else c['state_closed_text']
        state_icon = '●' if state == 'open' else '✓'
        state_label = 'Open' if state == 'open' else 'Closed'

        # Labels HTML
        labels_html = ''
        for label in labels:
            text_color, bg_color = self._get_label_color(label)
            labels_html += f'''
            <span class="label" style="background-color: {bg_color}; color: {text_color}; border-color: {text_color};">
                {escape(label)}
            </span>
            '''

        # Sidebar HTML
        sidebar_html = self._generate_sidebar_html(assignee, labels, milestone)

        # Comments HTML
        comments_html = ''
        for i, comment in enumerate(comments, 1):
            comment_date = self._format_date(comment.get('created_at', ''))
            comment_body = self._render_markdown_to_html(comment.get('body', ''))
            comments_html += f'''
            <div class="comment">
                <div class="comment-header">
                    <span class="comment-author">Comment {i}</span>
                    <span class="comment-date">{comment_date}</span>
                </div>
                <div class="comment-body markdown-body">
                    {comment_body}
                </div>
            </div>
            '''

        # Complete HTML document
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)} · {jira_key}</title>
    <link rel="stylesheet" href="../github-css/primer.css">
    <link rel="stylesheet" href="../github-css/github-markdown.css">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: {c['text_primary']};
            background-color: {c['bg_secondary']};
        }}

        .container {{
            max-width: 1280px;
            margin: 0 auto;
            padding: 24px;
        }}

        .header {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }}

        .issue-number {{
            font-size: 32px;
            font-weight: 300;
            color: {c['text_secondary']};
            margin-bottom: 8px;
        }}

        .issue-title {{
            font-size: 32px;
            font-weight: 600;
            line-height: 1.25;
            margin-bottom: 16px;
            word-wrap: break-word;
        }}

        .issue-meta {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .state-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 5px 12px;
            border-radius: 24px;
            font-size: 14px;
            font-weight: 500;
            background-color: {state_bg};
            color: {state_text};
        }}

        .issue-date {{
            color: {c['text_secondary']};
        }}

        .main-content {{
            display: grid;
            grid-template-columns: 1fr 296px;
            gap: 16px;
        }}

        .issue-body-container {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
        }}

        /* markdown-body class from github-markdown.css handles all content styling */
        .issue-body {{
            padding: 16px;
        }}

        .sidebar {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 16px;
            align-self: flex-start;
        }}

        .sidebar-section {{
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid {c['border_muted']};
        }}

        .sidebar-section:last-child {{
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }}

        .sidebar-title {{
            font-size: 12px;
            font-weight: 600;
            color: {c['text_secondary']};
            margin-bottom: 8px;
        }}

        .sidebar-value {{
            color: {c['text_primary']};
        }}

        .sidebar-none {{
            color: {c['text_muted']};
            font-style: italic;
        }}

        .label {{
            display: inline-block;
            padding: 0 7px;
            font-size: 12px;
            font-weight: 500;
            line-height: 18px;
            border-radius: 24px;
            border: 1px solid;
            margin: 2px;
        }}

        .comments-section {{
            margin-top: 16px;
        }}

        .comment {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            margin-bottom: 16px;
        }}

        .comment-header {{
            padding: 8px 16px;
            background-color: {c['bg_secondary']};
            border-bottom: 1px solid {c['border']};
            border-radius: 6px 6px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .comment-author {{
            font-weight: 600;
        }}

        .comment-date {{
            color: {c['text_secondary']};
            font-size: 12px;
        }}

        /* markdown-body class from github-markdown.css handles all content styling */
        .comment-body {{
            padding: 16px;
        }}

        @media (max-width: 768px) {{
            .main-content {{
                grid-template-columns: 1fr;
            }}

            .sidebar {{
                order: -1;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="issue-number">#{jira_key}</div>
            <h1 class="issue-title">{escape(title)}</h1>
            <div class="issue-meta">
                <span class="state-badge">{state_icon} {state_label}</span>
                <span class="issue-date">opened on {self._format_date(created_at)}</span>
                {f'<span class="issue-date">· closed on {self._format_date(closed_at)}</span>' if closed_at else ''}
            </div>
        </div>

        <div class="main-content">
            <div>
                <div class="issue-body-container">
                    <div class="issue-body markdown-body">
                        {self._render_markdown_to_html(body)}
                    </div>
                </div>

                {f'<div class="comments-section">{comments_html}</div>' if comments else ''}
            </div>

            {sidebar_html}
        </div>
    </div>
</body>
</html>'''

        return html

    def _generate_sidebar_html(self, assignee, labels, milestone):
        """Generate sidebar HTML with issue metadata."""
        c = self.COLORS

        # Assignee section
        assignee_html = f'<span class="sidebar-value">@{escape(assignee)}</span>' if assignee else '<span class="sidebar-none">No one assigned</span>'

        # Labels section
        if labels:
            labels_html = '<div>'
            for label in labels:
                text_color, bg_color = self._get_label_color(label)
                labels_html += f'<span class="label" style="background-color: {bg_color}; color: {text_color}; border-color: {text_color};">{escape(label)}</span>'
            labels_html += '</div>'
        else:
            labels_html = '<span class="sidebar-none">None yet</span>'

        # Milestone section
        milestone_html = f'<span class="sidebar-value">{escape(str(milestone))}</span>' if milestone else '<span class="sidebar-none">No milestone</span>'

        sidebar = f'''
        <div class="sidebar">
            <div class="sidebar-section">
                <div class="sidebar-title">Assignees</div>
                {assignee_html}
            </div>
            <div class="sidebar-section">
                <div class="sidebar-title">Labels</div>
                {labels_html}
            </div>
            <div class="sidebar-section">
                <div class="sidebar-title">Milestone</div>
                {milestone_html}
            </div>
        </div>
        '''

        return sidebar

    def generate_index_html(self, dry_run_folder, index_data):
        """Generate index.html listing all issues."""
        c = self.COLORS

        # Calculate statistics
        total_issues = len(index_data)
        open_issues = sum(1 for d in index_data if d['state'] == 'open')
        closed_issues = sum(1 for d in index_data if d['state'] == 'closed')

        # Count labels
        all_labels = {}
        for issue_data in index_data:
            for label in issue_data.get('labels', []):
                all_labels[label] = all_labels.get(label, 0) + 1

        # Generate issue rows
        rows_html = ''
        for issue_data in index_data:
            jira_key = issue_data['jira_key']
            title = escape(issue_data['title'])
            state = issue_data['state']
            labels = issue_data.get('labels', [])
            created = self._format_date(issue_data.get('created_at', ''))

            state_icon = '●' if state == 'open' else '✓'
            state_color = c['state_open_bg'] if state == 'open' else c['state_closed_bg']

            labels_html = ''
            for label in labels[:3]:  # Show max 3 labels in table
                text_color, bg_color = self._get_label_color(label)
                labels_html += f'<span class="label" style="background-color: {bg_color}; color: {text_color}; border-color: {text_color};">{escape(label)}</span>'

            if len(labels) > 3:
                labels_html += f'<span class="label-more">+{len(labels) - 3} more</span>'

            rows_html += f'''
            <tr>
                <td>
                    <span class="state-indicator" style="color: {state_color};">{state_icon}</span>
                </td>
                <td>
                    <a href="{jira_key}.html" class="issue-link">{jira_key}</a>
                </td>
                <td>
                    <a href="{jira_key}.html" class="issue-title-link">{title}</a>
                    <div class="issue-labels">{labels_html}</div>
                </td>
                <td class="issue-date">{created}</td>
            </tr>
            '''

        # Generate labels list
        labels_list_html = ''
        for label, count in sorted(all_labels.items(), key=lambda x: x[1], reverse=True):
            text_color, bg_color = self._get_label_color(label)
            labels_list_html += f'''
            <div class="label-stat">
                <span class="label" style="background-color: {bg_color}; color: {text_color}; border-color: {text_color};">{escape(label)}</span>
                <span class="label-count">{count}</span>
            </div>
            '''

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Issues Index - Dry Run Output</title>
    <link rel="stylesheet" href="github-css/primer.css">
    <link rel="stylesheet" href="github-css/github-markdown.css">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: {c['text_primary']};
            background-color: {c['bg_secondary']};
        }}

        .container {{
            max-width: 1280px;
            margin: 0 auto;
            padding: 24px;
        }}

        .header {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 24px;
        }}

        h1 {{
            font-size: 32px;
            font-weight: 600;
            margin-bottom: 16px;
        }}

        .stats {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }}

        .stat {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .stat-label {{
            color: {c['text_secondary']};
        }}

        .stat-value {{
            font-weight: 600;
            font-size: 16px;
        }}

        .issues-table-container {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            margin-bottom: 24px;
            overflow: hidden;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            background-color: {c['bg_secondary']};
            border-bottom: 1px solid {c['border']};
        }}

        td {{
            padding: 12px 16px;
            border-bottom: 1px solid {c['border_muted']};
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover {{
            background-color: {c['bg_secondary']};
        }}

        .state-indicator {{
            font-size: 12px;
        }}

        .issue-link {{
            color: {c['text_secondary']};
            text-decoration: none;
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 12px;
        }}

        .issue-link:hover {{
            color: {c['link']};
        }}

        .issue-title-link {{
            color: {c['text_primary']};
            text-decoration: none;
            font-weight: 500;
        }}

        .issue-title-link:hover {{
            color: {c['link']};
        }}

        .issue-labels {{
            margin-top: 4px;
        }}

        .label {{
            display: inline-block;
            padding: 0 7px;
            font-size: 12px;
            font-weight: 500;
            line-height: 18px;
            border-radius: 24px;
            border: 1px solid;
            margin-right: 4px;
        }}

        .label-more {{
            font-size: 12px;
            color: {c['text_secondary']};
        }}

        .issue-date {{
            color: {c['text_secondary']};
            font-size: 12px;
            white-space: nowrap;
        }}

        .labels-section {{
            background-color: {c['bg_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 24px;
        }}

        .labels-section h2 {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 16px;
        }}

        .labels-grid {{
            display: grid;
            gap: 8px;
        }}

        .label-stat {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
        }}

        .label-count {{
            color: {c['text_secondary']};
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Issues Index</h1>
            <div class="stats">
                <div class="stat">
                    <span class="stat-label">Total:</span>
                    <span class="stat-value">{total_issues}</span>
                </div>
                <div class="stat">
                    <span class="stat-label" style="color: {c['state_open_bg']};">● Open:</span>
                    <span class="stat-value">{open_issues}</span>
                </div>
                <div class="stat">
                    <span class="stat-label" style="color: {c['state_closed_bg']};">✓ Closed:</span>
                    <span class="stat-value">{closed_issues}</span>
                </div>
            </div>
        </div>

        <div class="issues-table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 40px;"></th>
                        <th style="width: 120px;">Issue</th>
                        <th>Title</th>
                        <th style="width: 120px;">Created</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
'''

        # Add labels section if there are any labels
        if all_labels:
            html += f'''
        <div class="labels-section">
            <h2>Labels</h2>
            <div class="labels-grid">
                {labels_list_html}
            </div>
        </div>
'''

        html += '''
    </div>
</body>
</html>'''

        # Write index.html
        index_file = os.path.join(dry_run_folder, 'index.html')
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(html)

        return index_file


def main():
    """Command-line interface for the HTML generator."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python html_generator.py <dry-run-folder>")
        print("   or: python html_generator.py <json-file>")
        sys.exit(1)

    path = sys.argv[1]
    generator = GitHubHTMLGenerator()

    if os.path.isdir(path):
        # Generate HTML for all JSON files in the directory
        json_files = [f for f in os.listdir(path) if f.endswith('.json') and f != 'index.json']

        print(f"Generating HTML files for {len(json_files)} issues...")
        for json_file in json_files:
            json_path = os.path.join(path, json_file)
            html_file = generator.generate_html(json_path)
            print(f"Generated: {html_file}")

        # Generate index if we have the data
        index_json = os.path.join(path, 'index.json')
        if os.path.exists(index_json):
            with open(index_json, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            index_file = generator.generate_index_html(path, index_data)
            print(f"Generated: {index_file}")

    elif os.path.isfile(path):
        # Generate HTML for a single JSON file
        html_file = generator.generate_html(path)
        print(f"Generated: {html_file}")

    else:
        print(f"Error: {path} does not exist")
        sys.exit(1)


if __name__ == '__main__':
    main()
