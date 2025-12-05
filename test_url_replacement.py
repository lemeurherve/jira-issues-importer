#!/usr/bin/env python3
"""Test script to verify Jira URL replacement with redirection service."""

import re
from collections import namedtuple

# Mock config and project objects
Config = namedtuple('Config', ['redirection_service'])
Project = namedtuple('Project', ['name', 'config'])

def replace_jira_urls_with_redirection_service(s, project):
    """
    Replace Jira browse URLs with redirection service URLs if configured.
    Preserves query strings from the original URLs.
    Excludes links marked with 'original-jira-comment-link' class.

    Example: https://issues.jenkins.io/browse/INFRA-123?focusedId=456
             -> https://issue-redirect.jenkins.io/issue/INFRA/123?focusedId=456
    """
    if s is None or not project.config.redirection_service:
        return s if s is not None else ''

    # Pattern to match any Jira browse URL (with or without https://)
    # Uses negative lookbehind to exclude 'original-jira-comment-link' class links
    # Multiple lookbehinds handle cases with/without protocol in the href attribute
    pattern = (
        rf'(?<!<a class="original-jira-comment-link" href=")'
        rf'(?<!<a class="original-jira-comment-link" href="https://)'
        rf'(?<!<a class="original-jira-comment-link" href="http://)'
        rf'(?:https?://)?issues\.jenkins\.io/browse/{project.name}-(\d+)(\?[^\s<>"]*)?'
    )

    # Replace with redirection service URL + project name + issue number + query string (if present)
    issue_number_and_query = r'\1\2'
    replacement = f'{project.config.redirection_service}/{project.name}/{issue_number_and_query}'

    return re.sub(pattern, replacement, s)

def replace_plain_jira_keys_with_links(s, project):
    """
    Replace plain text issue key references with markdown links.

    Example: Plain text "INFRA-123" -> [INFRA-123](https://issue-redirect.jenkins.io/issue/INFRA/123)
    """
    if s is None or not project.config.redirection_service:
        return s if s is not None else ''

    plain_key_pattern = (
        rf'(?<!browse/)'  # Not after browse/
        rf'(?<!href=")'  # Not after href="
        rf'(?<!\[)'  # Not after [
        rf'(?<!\()'  # Not after (
        rf'(?<!>)'  # Not after > (inside HTML tags)
        rf'\b({project.name}-(\d+))\b'  # Match whole word PROJECT-NUMBER
        rf'(?!\])'  # Not before ]
        rf'(?!\))'  # Not before )
        rf'(?!<)'  # Not before < (before HTML tags)
    )

    def replace_plain_key(match):
        full_key = match.group(1)
        issue_number = match.group(2)
        link_url = f'{project.config.redirection_service}/{project.name}/{issue_number}'
        return f'[{full_key}]({link_url})'

    return re.sub(plain_key_pattern, replace_plain_key, s)


# Test configuration (no trailing slash - project name will be added)
test_config = Config(redirection_service='https://issue-redirect.jenkins.io/issue')
test_project = Project(name='INFRA', config=test_config)

test_cases = [
    # Basic URL with https - only INFRA project matches
    ('https://issues.jenkins.io/browse/INFRA-123', 'https://issue-redirect.jenkins.io/issue/INFRA/123'),

    # Basic URL with http
    ('http://issues.jenkins.io/browse/INFRA-456', 'https://issue-redirect.jenkins.io/issue/INFRA/456'),

    # URL without protocol
    ('issues.jenkins.io/browse/INFRA-789', 'https://issue-redirect.jenkins.io/issue/INFRA/789'),

    # Only INFRA project key matches (JENKINS and SECURITY are not replaced)
    ('https://issues.jenkins.io/browse/INFRA-123', 'https://issue-redirect.jenkins.io/issue/INFRA/123'),
    ('https://issues.jenkins.io/browse/JENKINS-456', 'https://issues.jenkins.io/browse/JENKINS-456'),
    ('https://issues.jenkins.io/browse/SECURITY-789', 'https://issues.jenkins.io/browse/SECURITY-789'),

    # URL in text context
    ('See https://issues.jenkins.io/browse/INFRA-123 for details', 'See https://issue-redirect.jenkins.io/issue/INFRA/123 for details'),

    # Multiple URLs in same text - only INFRA gets replaced
    ('Issue https://issues.jenkins.io/browse/JENKINS-1 and https://issues.jenkins.io/browse/INFRA-2',
     'Issue https://issues.jenkins.io/browse/JENKINS-1 and https://issue-redirect.jenkins.io/issue/INFRA/2'),

    # URL in HTML link - should be replaced
    ('<a class="no-jira-link-rewrite" href="https://issues.jenkins.io/browse/INFRA-123">link</a>',
     '<a class="no-jira-link-rewrite" href="https://issue-redirect.jenkins.io/issue/INFRA/123">link</a>'),

    # URL with original-jira-comment-link class - should NOT be replaced
    ('<a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-123">original link</a>',
     '<a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-123">original link</a>'),

    # URL with original-jira-comment-link and query string - should NOT be replaced
    ('<a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-456?focusedId=789#comment-789">original comment</a>',
     '<a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-456?focusedId=789#comment-789">original comment</a>'),

    # Regular HTML link - should be replaced
    ('<a href="https://issues.jenkins.io/browse/INFRA-999">INFRA-999</a>',
     '<a href="https://issue-redirect.jenkins.io/issue/INFRA/999">INFRA-999</a>'),

    # URL with query string - single parameter
    ('https://issues.jenkins.io/browse/INFRA-123?focusedId=456',
     'https://issue-redirect.jenkins.io/issue/INFRA/123?focusedId=456'),

    # URL with query string - multiple parameters
    ('https://issues.jenkins.io/browse/INFRA-789?focusedId=456&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel',
     'https://issue-redirect.jenkins.io/issue/INFRA/789?focusedId=456&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel'),

    # URL with query string in HTML link
    ('<a href="https://issues.jenkins.io/browse/INFRA-123?focusedId=999#comment-999">comment link</a>',
     '<a href="https://issue-redirect.jenkins.io/issue/INFRA/123?focusedId=999#comment-999">comment link</a>'),

    # URL with complex query string (from actual comment links)
    ('https://issues.jenkins.io/browse/INFRA-123?focusedId=457400&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-457400',
     'https://issue-redirect.jenkins.io/issue/INFRA/123?focusedId=457400&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-457400'),

    # URL without query string followed by text
    ('https://issues.jenkins.io/browse/INFRA-123 and more text',
     'https://issue-redirect.jenkins.io/issue/INFRA/123 and more text'),

    # URL with query string followed by text
    ('https://issues.jenkins.io/browse/INFRA-123?id=456 and more',
     'https://issue-redirect.jenkins.io/issue/INFRA/123?id=456 and more'),
]

# Test cases for plain text issue key replacement
plain_text_test_cases = [
    # Plain text issue keys should become markdown links
    ('See INFRA-123 for details',
     'See [INFRA-123](https://issue-redirect.jenkins.io/issue/INFRA/123) for details'),

    # Multiple plain text keys in same string
    ('Related to INFRA-1, INFRA-2, and INFRA-3',
     'Related to [INFRA-1](https://issue-redirect.jenkins.io/issue/INFRA/1), [INFRA-2](https://issue-redirect.jenkins.io/issue/INFRA/2), and [INFRA-3](https://issue-redirect.jenkins.io/issue/INFRA/3)'),

    # Different project key should not match
    ('JENKINS-456 should not match', 'JENKINS-456 should not match'),

    # Already in markdown link format - should not be modified
    ('[INFRA-123](https://example.com)', '[INFRA-123](https://example.com)'),

    # Already in HTML link - should not be modified
    ('<a href="url">INFRA-456</a>', '<a href="url">INFRA-456</a>'),

    # Mixed: some plain text, some already linked
    ('See INFRA-100 and [INFRA-200](url)',
     'See [INFRA-100](https://issue-redirect.jenkins.io/issue/INFRA/100) and [INFRA-200](url)'),
]

# Comprehensive mixed test cases - combining all replacement types
def test_comprehensive_replacement(s, project):
    """Apply both URL and plain text replacements like _clean_html does"""
    # First replace URLs
    s = replace_jira_urls_with_redirection_service(s, project)
    # Then replace plain text keys
    s = replace_plain_jira_keys_with_links(s, project)
    return s

mixed_test_cases = [
    # Test 1: Mix of plain text keys and full URLs
    (
        'See INFRA-1 and https://issues.jenkins.io/browse/INFRA-2 for details',
        'See [INFRA-1](https://issue-redirect.jenkins.io/issue/INFRA/1) and https://issue-redirect.jenkins.io/issue/INFRA/2 for details'
    ),

    # Test 2: Plain text, URL, and comment link (with query string)
    (
        'Issue INFRA-100 relates to https://issues.jenkins.io/browse/INFRA-200?focusedId=300',
        'Issue [INFRA-100](https://issue-redirect.jenkins.io/issue/INFRA/100) relates to https://issue-redirect.jenkins.io/issue/INFRA/200?focusedId=300'
    ),

    # Test 3: With original-jira-comment-link (should NOT be rewritten)
    (
        'See INFRA-1 and <a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-2?focusedId=3">original</a>',
        'See [INFRA-1](https://issue-redirect.jenkins.io/issue/INFRA/1) and <a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-2?focusedId=3">original</a>'
    ),

    # Test 4: Mix with no-jira-link-rewrite (should be rewritten)
    (
        'Plain INFRA-10, link <a class="no-jira-link-rewrite" href="https://issues.jenkins.io/browse/INFRA-20">here</a>, and INFRA-30',
        'Plain [INFRA-10](https://issue-redirect.jenkins.io/issue/INFRA/10), link <a class="no-jira-link-rewrite" href="https://issue-redirect.jenkins.io/issue/INFRA/20">here</a>, and [INFRA-30](https://issue-redirect.jenkins.io/issue/INFRA/30)'
    ),

    # Test 5: Multiple plain text keys, multiple URLs, mixed projects
    (
        'INFRA-1, INFRA-2, JENKINS-3, https://issues.jenkins.io/browse/INFRA-4, https://issues.jenkins.io/browse/JENKINS-5',
        '[INFRA-1](https://issue-redirect.jenkins.io/issue/INFRA/1), [INFRA-2](https://issue-redirect.jenkins.io/issue/INFRA/2), JENKINS-3, https://issue-redirect.jenkins.io/issue/INFRA/4, https://issues.jenkins.io/browse/JENKINS-5'
    ),

    # Test 6: Complex real-world example with all types
    (
        'This issue INFRA-100 is related to https://issues.jenkins.io/browse/INFRA-200. '
        'See also <a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-300?focusedId=400">comment</a> '
        'and <a class="no-jira-link-rewrite" href="https://issues.jenkins.io/browse/INFRA-500">INFRA-500</a>. '
        'Also mentioned: INFRA-600, JENKINS-700.',
        'This issue [INFRA-100](https://issue-redirect.jenkins.io/issue/INFRA/100) is related to https://issue-redirect.jenkins.io/issue/INFRA/200. '
        'See also <a class="original-jira-comment-link" href="https://issues.jenkins.io/browse/INFRA-300?focusedId=400">comment</a> '
        'and <a class="no-jira-link-rewrite" href="https://issue-redirect.jenkins.io/issue/INFRA/500">INFRA-500</a>. '
        'Also mentioned: [INFRA-600](https://issue-redirect.jenkins.io/issue/INFRA/600), JENKINS-700.'
    ),

    # Test 7: Already has markdown links mixed with plain text
    (
        'See INFRA-1, [INFRA-2](existing-url), and INFRA-3',
        'See [INFRA-1](https://issue-redirect.jenkins.io/issue/INFRA/1), [INFRA-2](existing-url), and [INFRA-3](https://issue-redirect.jenkins.io/issue/INFRA/3)'
    ),

    # Test 8: Inside HTML content (should not replace inside tags)
    (
        '<a href="url">INFRA-1</a> but INFRA-2 outside',
        '<a href="url">INFRA-1</a> but [INFRA-2](https://issue-redirect.jenkins.io/issue/INFRA/2) outside'
    ),
]

print("Testing Jira URL replacement...")
print("=" * 80)

all_passed = True
for i, (input_text, expected) in enumerate(test_cases, 1):
    result = replace_jira_urls_with_redirection_service(input_text, test_project)
    passed = result == expected
    all_passed = all_passed and passed

    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\nTest {i}: {status}")
    print(f"  Input:    {input_text}")
    print(f"  Expected: {expected}")
    if not passed:
        print(f"  Got:      {result}")

print("\n" + "=" * 80)
if all_passed:
    print("All URL replacement tests passed! ✓")
else:
    print("Some URL replacement tests failed! ✗")

print("\n\nTesting plain text issue key replacement...")
print("=" * 80)

plain_text_passed = True
for i, (input_text, expected) in enumerate(plain_text_test_cases, 1):
    result = replace_plain_jira_keys_with_links(input_text, test_project)
    passed = result == expected
    plain_text_passed = plain_text_passed and passed

    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\nTest {i}: {status}")
    print(f"  Input:    {input_text}")
    print(f"  Expected: {expected}")
    if not passed:
        print(f"  Got:      {result}")

print("\n" + "=" * 80)
if plain_text_passed:
    print("All plain text replacement tests passed! ✓")
else:
    print("Some plain text replacement tests failed! ✗")

print("\n\nTesting comprehensive mixed scenarios...")
print("=" * 80)

mixed_passed = True
for i, (input_text, expected) in enumerate(mixed_test_cases, 1):
    result = test_comprehensive_replacement(input_text, test_project)
    passed = result == expected
    mixed_passed = mixed_passed and passed

    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\nTest {i}: {status}")
    if len(input_text) > 80:
        print(f"  Input:    {input_text[:80]}...")
    else:
        print(f"  Input:    {input_text}")
    if not passed:
        if len(expected) > 80:
            print(f"  Expected: {expected[:80]}...")
        else:
            print(f"  Expected: {expected}")
        if len(result) > 80:
            print(f"  Got:      {result[:80]}...")
        else:
            print(f"  Got:      {result}")

print("\n" + "=" * 80)
if mixed_passed:
    print("All comprehensive mixed tests passed! ✓")
else:
    print("Some comprehensive mixed tests failed! ✗")

print("\n" + "=" * 80)
print("FINAL SUMMARY:")
print(f"  URL replacement tests:        {'✓ PASS' if all_passed else '✗ FAIL'}")
print(f"  Plain text replacement tests: {'✓ PASS' if plain_text_passed else '✗ FAIL'}")
print(f"  Comprehensive mixed tests:    {'✓ PASS' if mixed_passed else '✗ FAIL'}")
print("=" * 80)

if not all_passed or not plain_text_passed or not mixed_passed:
    exit(1)
