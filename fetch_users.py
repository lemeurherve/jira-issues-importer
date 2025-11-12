#!/usr/bin/env python3

import os
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import time
from urllib.parse import urljoin

# Configuration
JIRA_SERVER = os.getenv('JIRA_MIGRATION_JIRA_URL', 'https://issues.jenkins.io')
USER_IDS_FILE = os.getenv('USER_IDS_FILE', 'jira_user_ids.txt')
OUTPUT_FILE = os.getenv('OUTPUT_FILE', 'jira_users.json')
AVATARS_DIR = 'avatars'
DELAY_SECONDS = float(os.getenv('DELAY_SECONDS', '0.5'))  # Delay between requests to avoid rate limiting

# Authentication - supports both cookies and basic auth
JIRA_COOKIE = os.getenv('JIRA_COOKIE', '')  # e.g., "JSESSIONID=xxxxx"
JIRA_USERNAME = os.getenv('JIRA_USERNAME', '')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD', '')


def get_session():
    """Create a requests session with authentication."""
    session = requests.Session()

    if JIRA_COOKIE:
        # Parse cookie string (format: "name=value" or "name1=value1; name2=value2")
        cookies = {}
        for cookie in JIRA_COOKIE.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                cookies[name] = value
        session.cookies.update(cookies)
        print("Using cookie authentication")
    elif JIRA_USERNAME and JIRA_PASSWORD:
        session.auth = (JIRA_USERNAME, JIRA_PASSWORD)
        print("Using basic authentication")
    else:
        print("Warning: No authentication configured. Some pages may be inaccessible.")

    # Set a user agent to avoid being blocked
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    return session


def fetch_user_profile(session, user_id):
    """Fetch and parse a user profile page."""
    # JIRAUSER* IDs need to use ?id= parameter instead of ?name=
    param = 'id' if user_id.startswith('JIRAUSER') else 'name'
    url = f'{JIRA_SERVER}/secure/ViewProfile.jspa?{param}={user_id}'
    print(f"Fetching profile for {user_id}...")

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()

        if 'login' in response.url.lower() or 'Log in to Jira' in response.text:
            print(f"  ⚠️  Authentication required for {user_id}")
            return None

        return parse_user_profile(response.text, user_id, url)

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error fetching {user_id}: {e}")
        return None


def parse_user_profile(html_content, user_id, profile_url):
    """Parse user profile HTML and extract all information."""
    soup = BeautifulSoup(html_content, 'html.parser')

    user_data = {
        'id': user_id,
        'profile_url': profile_url,
        'details': {},
        'sections': {}
    }

    # Extract user name from page title or heading
    title = soup.find('title')
    if title:
        user_data['page_title'] = title.text.strip()

    # Find the main profile heading (usually contains the full name)
    profile_heading = soup.find('h1', class_='page-title')
    if not profile_heading:
        profile_heading = soup.find('h1')

    if profile_heading:
        user_data['full_name'] = profile_heading.text.strip()

    # Extract avatar information
    avatar_img = soup.find('img', class_='userLogo')
    if not avatar_img:
        avatar_img = soup.find('img', {'alt': lambda x: x and 'Avatar' in x})

    if avatar_img and avatar_img.get('src'):
        avatar_url = avatar_img['src']
        if avatar_url.startswith('//'):
            avatar_url = 'https:' + avatar_url
        elif avatar_url.startswith('/'):
            avatar_url = urljoin(JIRA_SERVER, avatar_url)
        user_data['avatar_url'] = avatar_url

    # Extract email from mailto links
    mailto_link = soup.find('a', href=re.compile(r'^mailto:'))
    if mailto_link:
        user_data['email'] = mailto_link['href'].replace('mailto:', '')

    # Extract username (often in a specific element)
    username_elem = soup.find('span', class_='user-hover')
    if username_elem:
        user_data['username'] = username_elem.get('data-username') or username_elem.text.strip()

    # Extract all profile sections (like "Details", "Activity", etc.)
    # Look for definition lists (dl) which are common in JIRA profiles
    dl_elements = soup.find_all('dl')
    for dl in dl_elements:
        section_data = {}
        dt_elements = dl.find_all('dt')
        dd_elements = dl.find_all('dd')

        for dt, dd in zip(dt_elements, dd_elements):
            key = dt.text.strip().rstrip(':')
            value = dd.text.strip()
            section_data[key] = value

            # Also store in top-level details for common fields
            if key.lower() in ['username', 'full name', 'email', 'groups', 'login count', 'last login']:
                user_data['details'][key.lower().replace(' ', '_')] = value

        if section_data:
            user_data['sections']['profile_details'] = section_data

    # Extract all tables (may contain additional information)
    tables = soup.find_all('table')
    for i, table in enumerate(tables):
        table_data = []
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if cells:
                row_data = [cell.text.strip() for cell in cells]
                table_data.append(row_data)

        if table_data:
            user_data['sections'][f'table_{i}'] = table_data

    # Extract any additional structured data
    # Look for divs with id or class that might contain user info
    user_profile_div = soup.find('div', id='user-profile-panel')
    if not user_profile_div:
        user_profile_div = soup.find('div', class_='profile-panel')

    if user_profile_div:
        # Extract all text content organized by subsections
        subsections = user_profile_div.find_all(['div', 'section'], class_=True)
        for subsection in subsections:
            class_name = ' '.join(subsection.get('class', []))
            if class_name and subsection.text.strip():
                user_data['sections'][class_name] = subsection.text.strip()

    return user_data


def download_avatar(session, user_id, avatar_url, avatars_dir):
    """Download user avatar image."""
    if not avatar_url:
        return None

    try:
        # Determine file extension from URL
        ext = '.png'
        if '.jpg' in avatar_url or '.jpeg' in avatar_url:
            ext = '.jpg'
        elif '.gif' in avatar_url:
            ext = '.gif'

        filename = f"{user_id}{ext}"
        filepath = avatars_dir / filename

        # Download avatar
        response = session.get(avatar_url, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"  ✓ Downloaded avatar: {filename}")
        return filename

    except Exception as e:
        print(f"  ⚠️  Failed to download avatar: {e}")
        return None


def main():
    """Main function to orchestrate the scraping process."""
    print("=== JIRA User Profile Scraper ===\n")

    # Create avatars directory
    avatars_dir = Path(AVATARS_DIR)
    avatars_dir.mkdir(exist_ok=True)
    print(f"Avatar directory: {avatars_dir.absolute()}\n")

    # Read user IDs from file
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ Error: User IDs file '{USER_IDS_FILE}' not found.")
        print(f"   Please create a file with one user ID per line.")
        return

    print(f"Found {len(user_ids)} user IDs to process\n")

    # Create session
    session = get_session()

    # Collect all user data
    all_users = []

    for i, user_id in enumerate(user_ids, 1):
        print(f"[{i}/{len(user_ids)}] Processing {user_id}")

        # Fetch and parse profile
        user_data = fetch_user_profile(session, user_id)

        if user_data:
            # Download avatar
            if 'avatar_url' in user_data:
                avatar_filename = download_avatar(
                    session,
                    user_id,
                    user_data['avatar_url'],
                    avatars_dir
                )
                if avatar_filename:
                    user_data['avatar_filename'] = avatar_filename

            all_users.append(user_data)
            print(f"  ✓ Successfully processed {user_id}")

        # Rate limiting
        if i < len(user_ids):  # Don't delay after the last one
            time.sleep(DELAY_SECONDS)

        print()

    # Save to JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_users, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Complete! Processed {len(all_users)}/{len(user_ids)} users")
    print(f"📄 Output saved to: {OUTPUT_FILE}")
    print(f"🖼️  Avatars saved to: {avatars_dir.absolute()}")


if __name__ == '__main__':
    main()
