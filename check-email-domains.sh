#!/usr/bin/env bash

# Usage: ./analyze_domains.sh emails.txt

: "${JIRA_MIGRATION_PARALLEL_COUNT:=100}"

file="${1}"
bad_domains_file="bad_domains_$(basename "${file}")"
valid_emails_file="valid_$(basename "${file}")"
invalid_emails_file="invalid_$(basename "${file}")"

# Known dead domains, separated by a space
known_invalid_domains="java.net"

# Make sure files start empty
: > "${bad_domains_file}"
: > "${valid_emails_file}"
: > "${invalid_emails_file}"

if [[ -z "${file}" || ! -f "${file}" ]]; then
    echo "Usage: ${0} <file_with_emails>"
    exit 1
fi

if ! command -v parallel >/dev/null 2>&1; then
    echo "Error: 'parallel' is required but not installed on this system." >&2
    echo "Install it first. On macOS: brew install parallel" >&2
    exit 1
fi

check_domain() {
    domain="${1}"

    mx_records="$(dig +short MX "${domain}" 2>/dev/null)"
    if [[ -z "${mx_records}" ]]; then
        printf '[INVALID]  %s does NOT resolve\n' "${domain}"
        printf '%s\n' "${domain}" >> "${bad_domains_file}"
    fi
}
export -f check_domain
export bad_domains_file

echo "Extracting and counting domains..."
echo "-----------------------------------"

# Extract all domains
domain_list="$(grep -Eo '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+' "${file}" \
    | sed 's/.*@//' \
    | tr '[:upper:]' '[:lower:]')"

# Total count
total="$(printf '%s\n' "${domain_list}" | wc -l)"

# Compute grouped counts (sorted desc)
# We keep counts above 2 only
domains="$(printf '%s\n' "${domain_list}" \
    | sort \
    | uniq -c \
    | awk '$1 > 2' \
    | sort -nr)"
    
# Print header
printf "%-30s %10s %10s\n" "Domain" "Count" "Percent"
printf "%-30s %10s %10s\n" "------" "-----" "-------"

# Print domain stats
printf '%s\n' "${domains}" | while IFS= read -r line; do
    count="$(printf '%s\n' "${line}" | awk '{print $1}')"
    domain="$(printf '%s\n' "${line}" | awk '{print $2}')"

    percent="$(awk -v c="${count}" -v t="${total}" 'BEGIN { printf "%.2f", (c/t)*100 }')"

    printf "%-30s %10s %9s%%\n" "${domain}" "${count}" "${percent}"
done


unique_domains="$(printf '%s\n' "${domain_list}" | sort -u)"
unique_domains_count="$(printf '%s\n' "${unique_domains}" | wc -l)"

echo ""
echo "(domains with less than 3 occurences not shown above)"
echo "------------------------------------------------"
echo "${total} emails in total"
echo "${unique_domains_count} unique domains"
echo "------------------------------------------------"
echo "Checking DNS for each domain..."
echo ""

printf '%s\n' "${unique_domains}" | parallel -j "${JIRA_MIGRATION_PARALLEL_COUNT}" check_domain {}

# Special case of domains we're sure they're dead
echo ""
for domain in ${known_invalid_domains}; do
    echo "Adding ${domain} known bad domain to ${bad_domains_file}"
    printf '%s\n' "${domain}" >> "${bad_domains_file}"
done
tmp=$(mktemp)
sort -u  "${bad_domains_file}" > "$tmp"
mv "$tmp" "${bad_domains_file}"

echo "------------------------------------------------"
echo "$(cat "${bad_domains_file}" | wc -l) invalid unique domains"
echo "------------------------------------------------"
echo "Filtering valid emails..."
echo ""

# Filter out invalid emails
while IFS= read -r email; do
    domain="$(echo ${email##*@} | sed 's/>//')"

    domain="$(printf '%s' "${domain}" | tr '[:upper:]' '[:lower:]')"

    # check if domain is in bad_domains_file
    if grep -Fxq "${domain}" "${bad_domains_file}"; then
        echo "${email} is invalid"
        printf '%s\n' "${email}" >> "${invalid_emails_file}"
    else
        printf '%s\n' "${email}" >> "${valid_emails_file}"
    fi
done < "${file}"

echo "------------------------------------------------"
echo "Valid emails written to:   ${valid_emails_file}"
echo "Invalid emails written to: ${invalid_emails_file}"
echo "------------------------------------------------"
echo "$(cat "${valid_emails_file}" | wc -l) valid emails"
echo "$(cat "${invalid_emails_file}" | wc -l) invalid emails"
echo "------------------------------------------------"
