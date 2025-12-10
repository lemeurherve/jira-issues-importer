#!/usr/bin/env bash

set -e -o pipefail

# Orchestration script for Jira to GitHub migration
# Processes multiple components sequentially from a mapping file

# Usage: ./orchestrate-migration.sh [--resume] <components-file>
# Example: ./orchestrate-migration.sh components.txt
# Example: ./orchestrate-migration.sh --resume components.txt

RESUME_MODE=false
COMPONENTS_FILE=""
CHECKPOINT_FILE=".migration-checkpoint"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --resume)
      RESUME_MODE=true
      shift
      ;;
    *)
      COMPONENTS_FILE="$1"
      shift
      ;;
  esac
done

# Validate arguments
if [ -z "$COMPONENTS_FILE" ]; then
  echo "Error: Components file not specified"
  echo "Usage: $0 [--resume] <components-file>"
  exit 1
fi

if [ ! -f "$COMPONENTS_FILE" ]; then
  echo "Error: Components file not found: $COMPONENTS_FILE"
  exit 1
fi

# Source environment configuration
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "Error: .env file not found in $SCRIPT_DIR"
  echo "Please create a .env file with required JIRA_MIGRATION_* variables"
  exit 1
fi

echo "Loading environment configuration from .env"
source "$SCRIPT_DIR/.env"

# Validate required environment variables
REQUIRED_VARS=(
  "JIRA_MIGRATION_JIRA_PROJECT_NAME"
  "JIRA_MIGRATION_JIRA_URL"
  "JIRA_MIGRATION_JIRA_USER"
  "JIRA_MIGRATION_JIRA_TOKEN"
  "JIRA_MIGRATION_GITHUB_NAME"
  "JIRA_MIGRATION_GITHUB_ACCESS_TOKEN"
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    echo "Error: Required environment variable $var is not set in .env"
    exit 1
  fi
done

# Set migration datetime once for consistency
export JIRA_MIGRATION_CURRENT_DATETIME=$(date +%Y%m%d-%H%M%S)

# Create logs directory if it doesn't exist
mkdir -p logs

# Load checkpoint if resuming
declare -A COMPLETED_COMPONENTS
if [ "$RESUME_MODE" = true ] && [ -f "$CHECKPOINT_FILE" ]; then
  echo "Resume mode enabled. Loading checkpoint..."
  while IFS= read -r component; do
    COMPLETED_COMPONENTS["$component"]=1
  done < "$CHECKPOINT_FILE"
  echo "Found ${#COMPLETED_COMPONENTS[@]} completed components in checkpoint"
fi

# Function to log with timestamp
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function to validate file exists
validate_file() {
  local file=$1
  local description=$2
  if [ ! -f "$file" ]; then
    log "ERROR: Expected output file not found: $file ($description)"
    exit 1
  fi
  log "✓ Validated: $file"
}

# Function to archive component outputs
archive_component_outputs() {
  local component=$1
  local archive_dir="logs/$component"
  
  log "Archiving outputs to $archive_dir"
  mkdir -p "$archive_dir"
  
  # Move mapping files
  if ls jira-keys-to-github-id*.txt 1> /dev/null 2>&1; then
    mv jira-keys-to-github-id*.txt "$archive_dir/" 2>/dev/null || true
  fi
  
  if [ -f "issue_jira_github_mapping.json" ]; then
    mv issue_jira_github_mapping.json "$archive_dir/"
  fi
  
  # Move watcher and remotelink files
  if ls combined-*.txt 1> /dev/null 2>&1; then
    mv combined-*.txt "$archive_dir/" 2>/dev/null || true
  fi
  
  # Move jira comments file
  if [ -f "jira-comments.txt" ]; then
    mv jira-comments.txt "$archive_dir/"
  fi
  
  log "✓ Archived outputs to $archive_dir"
}

# Function to cleanup temporary files
cleanup_temp_files() {
  log "Cleaning up temporary files"
  
  if [ -d "jira_output" ]; then
    rm -rf jira_output/*
    log "✓ Cleaned jira_output directory"
  fi
}

# Function to process a single component
process_component() {
  local component=$1
  local github_repo=$2
  local github_owner="$JIRA_MIGRATION_GITHUB_NAME"
  
  log "=================================================="
  log "Starting migration for component: $component"
  log "Target: $github_owner/$github_repo"
  log "=================================================="
  
  # Set component-specific environment variables
  export JIRA_MIGRATION_GITHUB_REPO="$component"
  export JIRA_MIGRATION_JQL_QUERY="project = ${JIRA_MIGRATION_JIRA_PROJECT_NAME} AND component in ($component) ORDER BY issuekey"
  export JIRA_MIGRATION_FILE_PATHS="jira_output/combined.xml"
  
  # Set non-interactive mode variables
  export JIRA_MIGRATION_START_FROM_INDEX=0
  export JIRA_MIGRATION_DRY_RUN=false
  export JIRA_MIGRATION_REFRESH_MAPPINGS=true
  
  log "JQL Query: $JIRA_MIGRATION_JQL_QUERY"
  
  # Step 1: Fetch issues from Jira
  log ""
  log "Step 1/8: Fetching issues from Jira..."
  python3 ./fetch_issues.py
  validate_file "jira_output/result-0.xml" "Jira issues XML"
  
  # Step 2: Concatenate XML results
  log ""
  log "Step 2/8: Concatenating XML results..."
  ./concatenate-xml-results.sh
  validate_file "jira_output/combined.xml" "Combined XML"
  
  # Clean up individual result files
  rm -f jira_output/result-*.xml
  log "✓ Cleaned up individual XML files"
  
  # Step 3: Retrieve watchers and remote links
  log ""
  log "Step 3/8: Retrieving watchers and remote links..."
  ./retrieve-watchers-and-remotelinks.sh
  validate_file "combined-remotelinks.txt" "Remote links"
  
  # Step 4: Enable GitHub Issues on repository
  log ""
  log "Step 4/8: Enabling GitHub Issues on repository..."
  gh api -X PATCH "repos/$github_owner/$github_repo" --field has_issues=true || true
  log "✓ GitHub Issues enabled (or already enabled)"
  
  # Step 5: Import issues to GitHub
  log ""
  log "Step 5/8: Importing issues to GitHub..."
  python3 ./main.py
  validate_file "jira-keys-to-github-id_${JIRA_MIGRATION_CURRENT_DATETIME}.txt" "Jira-to-GitHub mapping"
  
  # Step 6: Post-process epics
  log ""
  log "Step 6/8: Post-processing epic relationships..."
  ./post_process_epics.sh "$github_owner" "$github_repo"
  
  # Step 7: Post-process issue types
  log ""
  log "Step 7/8: Post-processing issue types..."
  ./post_process_issues.sh "$github_owner" "$github_repo"
  
  # Step 8: Add comments to Jira issues
  log ""
  log "Step 8/8: Adding migration comments to Jira..."
  export JIRA_GITHUB_MAPPING_FILE="jira-keys-to-github-id_${JIRA_MIGRATION_CURRENT_DATETIME}.txt"
  ./jira-commenter.sh
  
  # Archive outputs
  log ""
  archive_component_outputs "$component"
  
  # Cleanup temporary files
  cleanup_temp_files
  
  # Mark component as complete
  echo "$component" >> "$CHECKPOINT_FILE"
  
  log ""
  log "✓ Successfully completed migration for component: $component"
  log "=================================================="
  log ""
}

# Main processing loop
log "Starting orchestrated migration"
log "Components file: $COMPONENTS_FILE"
log "Resume mode: $RESUME_MODE"
log "Migration datetime: $JIRA_MIGRATION_CURRENT_DATETIME"
log ""

TOTAL_COMPONENTS=0
PROCESSED_COMPONENTS=0
SKIPPED_COMPONENTS=0

# Read and process components
while IFS=: read -r component github_repo || [ -n "$component" ]; do
  # Skip empty lines and comments
  [[ -z "$component" || "$component" =~ ^[[:space:]]*# ]] && continue
  
  # Trim whitespace
  component=$(echo "$component" | xargs)
  github_repo=$(echo "$github_repo" | xargs)
  
  TOTAL_COMPONENTS=$((TOTAL_COMPONENTS + 1))
  
  # Check if component already completed
  if [ "$RESUME_MODE" = true ] && [ -n "${COMPLETED_COMPONENTS[$component]}" ]; then
    log "Skipping already completed component: $component"
    SKIPPED_COMPONENTS=$((SKIPPED_COMPONENTS + 1))
    continue
  fi
  
  # Process the component with logging
  LOG_FILE="logs/${component}-${JIRA_MIGRATION_CURRENT_DATETIME}.log"
  process_component "$component" "$github_repo" 2>&1 | tee "$LOG_FILE"
  
  PROCESSED_COMPONENTS=$((PROCESSED_COMPONENTS + 1))
  
done < "$COMPONENTS_FILE"

log ""
log "=================================================="
log "Migration orchestration complete!"
log "Total components: $TOTAL_COMPONENTS"
log "Processed: $PROCESSED_COMPONENTS"
log "Skipped: $SKIPPED_COMPONENTS"
log "=================================================="
