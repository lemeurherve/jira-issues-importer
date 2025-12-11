#!/usr/bin/env bash
set -euo pipefail

# Script to generate a report of all epics and their epic link counts in Jira
# GitHub has a limit of 100 sub-issues per parent so best to adjust these in Jira prior to migration
# Usage: ./jira-epic-stats.sh

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
fi

# Validate required environment variables
: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing Jira project name (e.g., JENKINS)}"
: "${JIRA_MIGRATION_JIRA_URL:? Missing Jira base URL (e.g., https://issues.jenkins.io)}"
: "${JIRA_MIGRATION_JIRA_TOKEN:? Missing Jira token}"
: "${JIRA_MIGRATION_PARALLEL_COUNT:=100}"

# Check for required commands
if ! command -v flock >/dev/null 2>&1; then
    echo "Error: 'flock' is required but not installed on this system." >&2
    echo "Install it first. On macOS: brew install flock" >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "Error: 'jq' is required but not installed on this system." >&2
    echo "Install it first. On macOS: brew install jq" >&2
    exit 1
fi

# Check Jira connectivity
echo "Check ${JIRA_MIGRATION_JIRA_URL} connectivity"
response_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
    "${JIRA_MIGRATION_JIRA_URL}/rest/api/2/myself")

if [[ "${response_code}" != 200 ]]; then
    echo "Error: Unable to connect to Jira"
    exit 1
fi

echo "Connected to Jira successfully."
echo ""

# Temporary files
epics_file=$(mktemp)
results_file=$(mktemp)
progress_file=$(mktemp)

# Cleanup on exit
cleanup() {
    rm -f "${epics_file}" "${results_file}" "${progress_file}" "${progress_file}.lock"
}
trap cleanup EXIT

# Fetch all epics
echo "Fetching all epics from ${JIRA_MIGRATION_JIRA_PROJECT_NAME}..."
jql_query="project = ${JIRA_MIGRATION_JIRA_PROJECT_NAME} AND type = EPIC"
search_url="${JIRA_MIGRATION_JIRA_URL}/rest/api/2/search"

epics_json=$(curl -s \
    -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
    -H "Content-Type: application/json" \
    -G "${search_url}" \
    --data-urlencode "jql=${jql_query}" \
    --data-urlencode "maxResults=1000" \
    --data-urlencode "fields=key,summary")

# Extract epic keys and titles
echo "${epics_json}" | jq -r '.issues[] | "\(.key)|\(.fields.summary)"' > "${epics_file}"

total=$(wc -l < "${epics_file}" | tr -d ' ')

if [ "${total}" -eq 0 ]; then
    echo "No epics found in ${JIRA_MIGRATION_JIRA_PROJECT_NAME}"
    exit 0
fi

echo "Found ${total} epics"
echo "Parallel count: ${JIRA_MIGRATION_PARALLEL_COUNT}"
echo ""
echo "Counting epic links for each epic..."

# Initialize progress counter
echo 0 > "${progress_file}"

# Export variables for subshells
export JIRA_MIGRATION_JIRA_URL
export JIRA_MIGRATION_JIRA_TOKEN
export JIRA_MIGRATION_JIRA_PROJECT_NAME
export results_file
export progress_file
export total

# Progress update function
update_progress() {
    local current
    {
        flock 200

        # Read the current value
        current=$(cat "$progress_file")
        current=$((current + 1))

        # Write the updated value
        echo "$current" > "$progress_file"
    } 200>"$progress_file.lock"

    percent=$((100 * current / total))
    printf "\r[%s/%s | %s%%] Processing epics..." "$current" "$total" "$percent" >&2
}

export -f update_progress

# Process a single epic
process_epic() {
    local line="$1"
    local key="${line%%|*}"
    local title="${line#*|}"
    
    # Query for issues linked to this epic
    local epic_link_jql="project = ${JIRA_MIGRATION_JIRA_PROJECT_NAME} AND \"Epic Link\" = ${key}"
    local search_url="${JIRA_MIGRATION_JIRA_URL}/rest/api/2/search"
    
    local count_json=$(curl -s \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
        -H "Content-Type: application/json" \
        -G "${search_url}" \
        --data-urlencode "jql=${epic_link_jql}" \
        --data-urlencode "maxResults=0" \
        --data-urlencode "fields=key")
    
    local count=$(echo "${count_json}" | jq -r '.total // 0')
    
    # Write result to shared file
    echo "${key}|${title}|${count}" >> "${results_file}"
    
    update_progress
}

export -f process_epic

# Process all epics in parallel
# Use printf with null separator for BSD xargs compatibility
while IFS= read -r line; do
    printf '%s\0' "$line"
done < "${epics_file}" | xargs -0 -n1 -P"${JIRA_MIGRATION_PARALLEL_COUNT}" bash -c 'process_epic "$@"' _

echo "" >&2
echo "" >&2
echo "Processing complete. Generating report..." >&2

# Generate output file name with timestamp
output_file="epic-stats-$(date +%Y-%m-%d-%H%M%S).txt"

# Calculate summary statistics
total_epics=$(wc -l < "${results_file}" | tr -d ' ')
total_issues=0
zero_count=0
max_count=0
max_epic=""
min_count=999999
min_epic=""

while IFS='|' read -r key title count; do
    total_issues=$((total_issues + count))
    
    if [ "${count}" -eq 0 ]; then
        zero_count=$((zero_count + 1))
    fi
    
    if [ "${count}" -gt "${max_count}" ]; then
        max_count="${count}"
        max_epic="${key}"
    fi
    
    if [ "${count}" -lt "${min_count}" ]; then
        min_count="${count}"
        min_epic="${key}"
    fi
done < "${results_file}"

# Calculate average
if [ "${total_epics}" -gt 0 ]; then
    average=$((total_issues / total_epics))
else
    average=0
fi

# Function to create clickable link with ANSI escape sequences
make_link() {
    local key="$1"
    local url="${JIRA_MIGRATION_JIRA_URL}/browse/${key}"
    printf '\e]8;;%s\e\\%s\e]8;;\e\\' "${url}" "${key}"
}

# Generate report header (for both stdout and file)
report_header() {
    echo "=================================================="
    echo "Epic Link Count Report"
    echo "Project: ${JIRA_MIGRATION_JIRA_PROJECT_NAME}"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=================================================="
    echo ""
    echo "Summary Statistics:"
    echo "  Total Epics:        ${total_epics}"
    echo "  Total Linked Issues: ${total_issues}"
    echo "  Average Links/Epic:  ${average}"
    echo "  Epics with 0 Links:  ${zero_count}"
    echo "  Max Links:           ${max_count} (${max_epic})"
    echo "  Min Links:           ${min_count} (${min_epic})"
    echo ""
    echo "=================================================="
    echo ""
}

# Write header to both stdout and file
report_header | tee "${output_file}"

# Sort by count (descending), then by key, and format output
# Display to stdout with clickable links, save to file without ANSI codes
while IFS='|' read -r key title count; do
    # Determine plural
    if [ "${count}" -eq 1 ]; then
        plural="issue"
    else
        plural="issues"
    fi
    
    # Create clickable link for stdout
    link=$(make_link "${key}")
    
    # Format with clickable link for stdout: [JENKINS-12345]: Epic Title (42 issues)
    printf "%s: %s (%d %s)\n" "${link}" "${title}" "${count}" "${plural}"
    
    # Format without ANSI codes for file: JENKINS-12345: Epic Title (42 issues)
    printf "%s: %s (%d %s)\n" "${key}" "${title}" "${count}" "${plural}" >> "${output_file}"
done < <(sort -t'|' -k3 -nr -k1 "${results_file}")

echo "" | tee -a "${output_file}"
echo "Report saved to: ${output_file}"

