# JIRA User Profile Scraper

A Python script to scrape user profile information from JIRA instances, including user details, avatars, and all visible profile sections.

## Features

- Scrapes user profiles from JIRA user profile pages
- Extracts: user ID, username, full name, email, avatar URL, and all other profile information
- Downloads user avatar images to a local folder
- Supports authentication via cookies or username/password
- Outputs structured JSON with organized sections
- Respects rate limiting with configurable delays

## Setup

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Prepare User IDs File

Create a text file named `jira_user_ids.txt` with one user ID per line:

```
JIRAUSER134221
JIRAUSER123456
JIRAUSER789012
```

### 3. Configure Authentication

JIRA requires authentication to view user profiles. You have two options:

#### Option A: Cookie-based Authentication (Recommended)

This is the easiest method if you're already logged into JIRA:

1. Log in to JIRA in your web browser
2. Open Developer Tools (F12)
3. Go to Application (Chrome) or Storage (Firefox) > Cookies
4. Find and copy the `JSESSIONID` cookie value
5. Optionally copy other cookies like `atlassian.xsrf.token`
6. Set the environment variable:

```bash
export JIRA_COOKIE="JSESSIONID=your-session-id-here"
# Or with multiple cookies:
export JIRA_COOKIE="JSESSIONID=xxx; atlassian.xsrf.token=yyy"
```

#### Option B: Username/Password Authentication

```bash
export JIRA_USERNAME="your-username"
export JIRA_PASSWORD="your-password"
```

## Usage

### Quick Start

```bash
# Edit jira-users-collector.sh to add your authentication
# Then run:
bash jira-users-collector.sh
```

### Manual Execution

```bash
# Set environment variables
export JIRA_MIGRATION_JIRA_URL="https://issues.jenkins.io"
export JIRA_COOKIE="JSESSIONID=your-cookie-here"

# Run the scraper
python3 fetch_users.py
```

### Configuration Options

All configuration is done via environment variables:

- `JIRA_MIGRATION_JIRA_URL` - JIRA server URL (default: `https://issues.jenkins.io`)
- `USER_IDS_FILE` - Input file with user IDs (default: `jira_user_ids.txt`)
- `OUTPUT_FILE` - Output JSON file (default: `jira_users.json`)
- `DELAY_SECONDS` - Delay between requests in seconds (default: `0.5`)
- `JIRA_COOKIE` - Authentication cookie string
- `JIRA_USERNAME` - JIRA username for basic auth
- `JIRA_PASSWORD` - JIRA password for basic auth

## Output

### JSON Structure

The script creates a JSON file with the following structure:

```json
[
  {
    "id": "JIRAUSER134221",
    "profile_url": "https://issues.jenkins.io/secure/ViewProfile.jspa?id=JIRAUSER134221",
    "page_title": "User Profile - JIRA",
    "full_name": "John Doe",
    "username": "johndoe",
    "email": "john.doe@example.com",
    "avatar_url": "https://issues.jenkins.io/secure/useravatar?ownerId=JIRAUSER134221",
    "avatar_filename": "JIRAUSER134221.png",
    "details": {
      "username": "johndoe",
      "full_name": "John Doe",
      "email": "john.doe@example.com",
      "groups": "jira-users, jira-developers",
      "login_count": "1234",
      "last_login": "01/Jan/25 12:00 PM"
    },
    "sections": {
      "profile_details": {
        "Username": "johndoe",
        "Full Name": "John Doe",
        "Email": "john.doe@example.com"
      }
    }
  }
]
```

### Avatar Files

Avatar images are saved in the `avatars/` directory with filenames matching the user ID:

```
avatars/
  JIRAUSER134221.png
  JIRAUSER123456.jpg
  JIRAUSER789012.png
```

## Troubleshooting

### Authentication Failed

If you see "Authentication required" messages:
- Verify your cookie is still valid (they expire)
- Try copying a fresh cookie from your browser
- Alternatively, use username/password authentication

### Rate Limiting

If you're scraping many users and getting errors:
- Increase `DELAY_SECONDS`: `export DELAY_SECONDS="1.0"`
- The script includes automatic delays between requests

### Missing Information

Some fields may not be present on all user profiles:
- The script extracts all available information
- Missing fields will simply not appear in the JSON output

## Example

```bash
# Create user IDs file
cat > jira_user_ids.txt <<EOF
JIRAUSER134221
JIRAUSER100001
JIRAUSER100002
EOF

# Set authentication
export JIRA_COOKIE="JSESSIONID=abc123xyz"

# Run scraper
python3 fetch_users.py

# Check results
cat jira_users.json
ls -la avatars/
```

## Advanced Usage

### Custom Output Location

```bash
export OUTPUT_FILE="users_$(date +%Y%m%d).json"
python3 fetch_users.py
```

### Different JIRA Instance

```bash
export JIRA_MIGRATION_JIRA_URL="https://your-company.atlassian.net"
python3 fetch_users.py
```

## Notes

- The script respects rate limits with built-in delays
- Avatar downloads are optional and won't fail the entire process if they error
- All output uses UTF-8 encoding to support international characters
- The script is idempotent - you can run it multiple times safely
