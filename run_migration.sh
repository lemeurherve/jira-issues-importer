#!/bin/bash

# Default settings for start_from and Jira done ID
START_FROM="0"
JIRA_DONE_ID="3"

# Parse command line arguments
while getopts p:u:x:s:r:g: flag
do
    case "${flag}" in
        p) JIRA_PROJECT=${OPTARG};;
        u) JIRA_URL=${OPTARG};;
        x) XML_PATH=${OPTARG};;
        s) SECURITY_REPO=${OPTARG};;
        r) DEFAULT_REPO=${OPTARG};;
        g) GITHUB_ACCOUNT=${OPTARG};;
    esac
done

# Check if GITHUB_ACCOUNT is missing and print an error
if [ -z "$GITHUB_ACCOUNT" ]; then
    echo "Error: GitHub account name is required. Use the -g flag to specify the account name."
    exit 1
fi

# If XML_PATH is not provided, auto-detect XML files in the current directory
if [ -z "$XML_PATH" ]; then
    echo "No XML path provided. Searching for XML files in the current directory..."
    XML_FILES=$(find "$(pwd)" -maxdepth 1 -name "*.xml")
    if [ -z "$XML_FILES" ]; then
        echo "No XML files found in the current directory. Please ensure the XML file is in the same directory as this script."
        exit 1
    fi
    XML_PATH="$XML_FILES"
fi

# Display the provided values
echo "Security Repo: https://github.com/$GITHUB_ACCOUNT/$SECURITY_REPO"
echo "Default Repo: https://github.com/$GITHUB_ACCOUNT/$DEFAULT_REPO"
echo "GitHub Account: $GITHUB_ACCOUNT"
echo "Jira Project: $JIRA_PROJECT"
echo "XML Paths: $XML_PATH"
echo "Done Status ID: $JIRA_DONE_ID"
echo "Start from: $START_FROM"

# Request GitHub PAT from user input and display it for confirmation
read -p "Enter your GitHub Personal Access Token (PAT): " GITHUB_PAT
echo "GitHub PAT: $GITHUB_PAT"  # Display PAT to ensure it's correctly entered

# Set environment variables
export JIRA_MIGRATION_JIRA_PROJECT_NAME="$JIRA_PROJECT"
export JIRA_MIGRATION_JIRA_DONE_ID="$JIRA_DONE_ID"
export JIRA_MIGRATION_JIRA_URL="$JIRA_URL"
export JIRA_MIGRATION_FILE_PATHS="$XML_PATH"
export SECURITY_REPO_URL="https://github.com/$GITHUB_ACCOUNT/$SECURITY_REPO"
export DEFAULT_REPO_URL="https://github.com/$GITHUB_ACCOUNT/$DEFAULT_REPO"
export JIRA_MIGRATION_GITHUB_ACCESS_TOKEN="$GITHUB_PAT"

# Print the environment variables for debugging
echo "SECURITY_REPO_URL: $SECURITY_REPO_URL"
echo "DEFAULT_REPO_URL: $DEFAULT_REPO_URL"
echo "GITHUB_ACCOUNT: $GITHUB_ACCOUNT"

# Activate or create the virtual environment
if [ ! -d "jira_migration_venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv jira_migration_venv
fi

echo "Activating existing virtual environment..."
source jira_migration_venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run the Python migration script
echo "Running migration script in simulation mode..."
python3 main.py
