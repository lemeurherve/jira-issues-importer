#!/usr/bin/env bash

# JIRA User Profile Scraper
# This script runs the Python user profile scraper with proper environment variables

# Configuration
export JIRA_MIGRATION_JIRA_URL="https://issues.jenkins.io"
export USER_IDS_FILE="jira_user_ids.txt"
export OUTPUT_FILE="jira_users.json"
export DELAY_SECONDS="0.5"

# Authentication Method 1: Using cookies (recommended for already logged-in sessions)
# To get your cookie:
# 1. Log in to JIRA in your browser
# 2. Open Developer Tools (F12) > Application/Storage > Cookies
# 3. Find JSESSIONID or other session cookies and copy the value
# export JIRA_COOKIE="JSESSIONID=your-session-id-here; atlassian.xsrf.token=your-token-here"

# Authentication Method 2: Using username and password
# export JIRA_USERNAME="<your-jenkins-username>"
# export JIRA_PASSWORD="<your-jenkins-password>"

# Install dependencies if needed
# pip3 install -r requirements.txt

# Run the scraper
python3 fetch_users.py
