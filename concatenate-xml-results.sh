#!/bin/bash

folder="jira_output"
out="${folder}/combined.xml"

# 1. Write header from the first file (everything up to the first <item>)
awk '
    !header_done { print; if ($0 ~ /<item>/) header_done=1; next }
' "${folder}"/result-*.xml | sed '/<item>/q' | grep -v '<item>' > "$out"

# 2. Append all <item>…</item> entries from all files
for f in "${folder}"/result-*.xml; do
    echo "Concatenating ${f}..."
    awk '
        /<item>/,/<\/item>/ { print }
    ' "$f" >> "$out"
done

# 3. Add closing tags
echo "</channel>" >> "$out"
echo "</rss>" >> "$out"
