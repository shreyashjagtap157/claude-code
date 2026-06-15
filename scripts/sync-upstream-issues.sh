#!/usr/bin/env bash
# Sync upstream issues to fork
# Usage: bash scripts/sync-upstream-issues.sh
# Dependencies: gh (authenticated), jq

set -euo pipefail

UPSTREAM_REPO="anthropics/claude-code"
FORK_REPO="shreyashjagtap157/claude-code"
MARKER_PREFIX="upstream-issue"
SYNC_LABEL="synced-from-upstream"

info()  { printf "  [INFO] %s\n" "$1"; }
ok()    { printf "  [ OK ] %s\n" "$1"; }
skip()  { printf "  [SKIP] %s\n" "$1"; }
err()   { printf "  [ERR ] %s\n" "$1"; }

echo "=== Syncing issues from $UPSTREAM_REPO → $FORK_REPO ==="

# Pre-check: gh auth
gh auth status &>/dev/null || { err "Not authenticated. Run: gh auth login"; exit 1; }

# Fetch all upstream issues
info "Fetching upstream issues..."
upstream_json=$(gh issue list --repo "$UPSTREAM_REPO" --state all --json number,title,body,state,labels --limit 1000)
upstream_count=$(echo "$upstream_json" | jq 'length')
info "Found $upstream_count issues upstream"

# Fetch all fork issues
info "Checking fork for existing synced issues..."
fork_json=$(gh issue list --repo "$FORK_REPO" --state all --json number,body --limit 1000)

# Collect unique upstream labels and create them in fork if missing
info "Ensuring labels exist in fork..."
echo "$upstream_json" | jq -c '[.[].labels[]] | unique_by(.name) | .[]' | while read -r label; do
    label_name=$(echo "$label" | jq -r '.name')
    label_color=$(echo "$label" | jq -r '.color')
    label_desc=$(echo "$label" | jq -r '.description // ""')
    
    if ! gh label list --repo "$FORK_REPO" --limit 500 | grep -qi "^$label_name\b"; then
        gh label create "$label_name" --repo "$FORK_REPO" --color "$label_color" --description "$label_desc" 2>/dev/null && ok "Created label: $label_name" || info "Label $label_name exists (skipped)"
    fi
done

# Create sync label if missing
if ! gh label list --repo "$FORK_REPO" --limit 500 | grep -qi "^$SYNC_LABEL\b"; then
    gh label create "$SYNC_LABEL" --repo "$FORK_REPO" --color "C0C0C0" --description "Synced from upstream anthropics/claude-code" 2>/dev/null && ok "Created label: $SYNC_LABEL"
fi

# Process each upstream issue
echo "$upstream_json" | jq -c '.[]' | while read -r issue; do
    number=$(echo "$issue" | jq -r '.number')
    title=$(echo "$issue" | jq -r '.title')
    body=$(echo "$issue" | jq -r '.body')
    state=$(echo "$issue" | jq -r '.state')
    upstream_labels=$(echo "$issue" | jq -r '[.labels[].name] | join(",")')
    
    marker="<!-- $MARKER_PREFIX: $number -->"
    
    # Check if already synced
    existing=$(echo "$fork_json" | jq -r ".[] | select(.body != null and (.body | contains(\"$marker\"))) | .number" | head -1)
    
    if [ -n "$existing" ]; then
        skip "#$number → already synced as #$existing"
        continue
    fi
    
    info "Creating #$number: $title"
    
    # Build body with marker and upstream link
    new_body="${body}

---
*Synced from upstream issue [#${number}](https://github.com/${UPSTREAM_REPO}/issues/${number})*
${marker}"
    
    # Collect labels for --label flag
    label_args=""
    IFS=',' read -ra label_arr <<< "$upstream_labels"
    for lbl in "${label_arr[@]}"; do
        label_args="$label_args --label \"$lbl\""
    done
    label_args="$label_args --label \"$SYNC_LABEL\""
    
    # Create issue
    created=$(eval gh issue create --repo "\"$FORK_REPO\"" --title "\"$title\"" --body "\"$new_body\"" "$label_args" 2>&1)
    new_number=$(echo "$created" | grep -oE '[0-9]+$' | head -1)
    
    if [ -z "$new_number" ]; then
        err "Failed to create #$number: $created"
        continue
    fi
    
    ok "Created #$number as #$new_number"
    
    # Close if upstream was closed
    if [ "$state" = "CLOSED" ]; then
        gh issue close "$new_number" --repo "$FORK_REPO" --comment "This issue was closed in the upstream repository." 2>/dev/null
        ok "Closed #$new_number (upstream state was CLOSED)"
    fi
done

echo "=== Sync complete ==="
