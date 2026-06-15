# Sync upstream issues to fork (PowerShell version)
# Usage: pwsh scripts/sync-upstream-issues.ps1
# Dependencies: gh (authenticated)

$UPSTREAM_REPO = "anthropics/claude-code"
$FORK_REPO = "shreyashjagtap157/claude-code"
$MARKER_PREFIX = "upstream-issue"
$SYNC_LABEL = "synced-from-upstream"
$SYNCED_FILE = Join-Path $PSScriptRoot "synced-upstream-numbers.json"

Write-Host "=== Syncing issues from $UPSTREAM_REPO → $FORK_REPO ===" -ForegroundColor Cyan

# Pre-check gh auth
$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not authenticated. Run: gh auth login"
    exit 1
}

# Helper: retry a command block up to N times
function Invoke-WithRetry {
    param([ScriptBlock]$Block, [int]$MaxRetries = 3, [string]$Label = "operation")
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $result = & $Block
        if ($LASTEXITCODE -eq 0 -and $result) { return $result }
        if ($attempt -lt $MaxRetries) {
            $wait = $attempt * 3
            Write-Host "  [RETRY] $Label failed (attempt $attempt/$MaxRetries), retrying in ${wait}s..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds $wait
        }
    }
    Write-Host "  [FAIL] $Label failed after $MaxRetries attempts" -ForegroundColor Red
    return $null
}

# Step 1: Fetch all upstream issues with retry
Write-Host "Fetching upstream issues..." -ForegroundColor Yellow
$upstreamJson = Invoke-WithRetry -Block { gh issue list --repo $UPSTREAM_REPO --state all --json number,title,body,state,labels,createdAt --limit 1000 2>&1 | ConvertFrom-Json } -Label "fetch upstream issues"
if (-not $upstreamJson -or $upstreamJson.Count -eq 0) {
    Write-Host "No upstream issues found or failed to parse." -ForegroundColor Red
    exit 1
}
Write-Host "Found $($upstreamJson.Count) issues upstream" -ForegroundColor Green

# Step 2: Load previously synced upstream numbers from local tracking file
# This avoids needing to re-fetch all fork issue bodies (which exceeds --limit 1000).
Write-Host "Loading synced issues tracking file..." -ForegroundColor Yellow
$syncedNums = @()
if (Test-Path $SYNCED_FILE) {
    try { $syncedNums = Get-Content $SYNCED_FILE -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
    catch { Write-Host "  [WARN] Could not read $SYNCED_FILE, starting fresh" -ForegroundColor DarkYellow }
}
$syncedCount = if ($syncedNums -is [array]) { $syncedNums.Count } else { 0 }
Write-Host "Found $syncedCount previously synced issues" -ForegroundColor Green

# Step 3: Collect unique labels from upstream and ensure they exist in fork
Write-Host "Ensuring labels exist in fork..." -ForegroundColor Yellow
$allLabels = @()
foreach ($issue in $upstreamJson) {
    foreach ($label in $issue.labels) {
        $allLabels += [PSCustomObject]@{
            name = $label.name
            color = $label.color
            description = $label.description
        }
    }
}
$uniqueLabels = $allLabels | Sort-Object name -Unique
Write-Host "Upstream has $($uniqueLabels.Count) unique labels" -ForegroundColor DarkGray

# Get existing fork labels as an array of names
$existingRaw = gh label list --repo $FORK_REPO --limit 500 2>&1
$existingForkLabelNames = @()
if ($existingRaw -is [array]) {
    $existingForkLabelNames = $existingRaw | ForEach-Object { $_.Split("`t")[0] }
} elseif ($existingRaw -is [string] -and $existingRaw.Trim().Length -gt 0) {
    $existingForkLabelNames = @($existingRaw.Split("`t")[0])
}

$labelCreateOk = 0
$labelCreateFail = 0
foreach ($label in $uniqueLabels) {
    $labelName = $label.name
    if ($existingForkLabelNames -contains $labelName) {
        continue
    }

    $desc = if ($label.description) { $label.description } else { "" }
    if ($desc.Length -gt 0) {
        $result = gh label create $labelName --repo $FORK_REPO --color $label.color --description $desc 2>&1
    } else {
        $result = gh label create $labelName --repo $FORK_REPO --color $label.color 2>&1
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Created label: $labelName" -ForegroundColor Green
        $labelCreateOk++
    } else {
        Write-Host "  [ERR] Failed to create label '$labelName': $result" -ForegroundColor Red
        $labelCreateFail++
    }
}
Write-Host "Labels: $labelCreateOk created, $labelCreateFail failed" -ForegroundColor $(if ($labelCreateFail -gt 0) { "Red" } else { "DarkGray" })

# Create sync label if missing
if ($existingForkLabelNames -notcontains $SYNC_LABEL) {
    gh label create $SYNC_LABEL --repo $FORK_REPO --color "C0C0C0" --description "Synced from upstream anthropics/claude-code" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Created label: $SYNC_LABEL" -ForegroundColor Green
    }
}

# Build a set for O(1) lookup
$syncedSet = @{}
foreach ($n in $syncedNums) { $syncedSet[$n] = $true }

# Step 4: Sync each upstream issue
$created = 0
$skipped = 0
$failed = 0

foreach ($issue in $upstreamJson) {
    $number = $issue.number
    $title = $issue.title
    $body = $issue.body
    $state = $issue.state
    $marker = "<!-- ${MARKER_PREFIX}: $number -->"

    # Check if already synced
    if ($syncedSet.ContainsKey($number)) {
        Write-Host "  [SKIP] #${number} already synced" -ForegroundColor DarkGray
        $skipped++
        continue
    }

    # Build new body with marker and upstream link
    $newBody = @"
$body

---
*Synced from upstream issue [#${number}](https://github.com/${UPSTREAM_REPO}/issues/${number})*
${marker}
"@

    # Build label list
    $labelNames = @()
    foreach ($ln in $issue.labels.name) { if ($ln) { $labelNames += $ln } }
    $labelNames += $SYNC_LABEL

    $displayTitle = if ($title.Length -gt 70) { $title.Substring(0, 70) + "..." } else { $title }
    Write-Host "  [SYNC] Creating #${number}: $displayTitle" -ForegroundColor Yellow

    # Use gh api (not gh issue create) because the latter silently returns exit 0
    # when GitHub rate-limits content creation, making detection impossible.
    # gh api properly returns HTTP 403 for rate limiting.
    $jsonFile = [System.IO.Path]::GetTempFileName() + ".json"
    $payload = @{
        title  = $title
        body   = $newBody
        labels = @($labelNames)
    }
    $payloadJson = $payload | ConvertTo-Json -Compress -Depth 10
    [System.IO.File]::WriteAllText($jsonFile, $payloadJson, [System.Text.UTF8Encoding]::new($false))

    $newNumber = $null
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $result = gh api repos/$FORK_REPO/issues --method POST --input $jsonFile 2>&1
        $exit = $LASTEXITCODE
        if ($exit -eq 0) {
            $parsed = $result | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($parsed -and $parsed.number) {
                $newNumber = $parsed.number
            }
            break
        }
        # Check for rate limiting
        if ($result -match "secondary rate limit|403") {
            $backoff = [Math]::Min($attempt * 30, 300)
            Write-Host "  [RATE] Rate limited (attempt $attempt/10), waiting ${backoff}s..." -ForegroundColor Magenta
            Start-Sleep -Seconds $backoff
        } elseif ($attempt -lt 10) {
            $backoff = $attempt * 5
            Write-Host "  [RETRY] create #${number} (attempt $attempt/10), waiting ${backoff}s..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds $backoff
        }
    }

    Remove-Item -Force $jsonFile -ErrorAction SilentlyContinue

    if (-not $newNumber) {
        Write-Host "  [ERR ] Failed to create #${number}" -ForegroundColor Red
        $failed++
        continue
    }

    Write-Host "  [ OK ] Created as #$newNumber" -ForegroundColor Green
    $created++

    # Save synced number to tracking file
    $syncedNums += $number
    $syncedNums | ConvertTo-Json -Compress | Set-Content -Path $SYNCED_FILE -Encoding UTF8 -NoNewline

    Start-Sleep -Milliseconds 500

    if ($state -eq "CLOSED") {
        gh issue close $newNumber --repo $FORK_REPO --comment "This issue was closed in the upstream repository." 2>$null | Out-Null
        Write-Host "  [CLOS] Closed #$newNumber (upstream was CLOSED)" -ForegroundColor Magenta
    }

    # Delay between creates to avoid GitHub secondary rate limiting (content creation)
    Start-Sleep -Seconds 5
}

$totalColor = if ($failed -gt 0) { "Red" } else { "Green" }
Write-Host "=== Sync complete ===" -ForegroundColor Cyan
Write-Host "Created: $created | Skipped: $skipped | Failed: $failed" -ForegroundColor $totalColor
