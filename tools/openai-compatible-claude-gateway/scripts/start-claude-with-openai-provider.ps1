[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ClaudeArgs
)
$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $PSScriptRoot
$envFile = if ($env:GATEWAY_ENV_FILE) { $env:GATEWAY_ENV_FILE } else { Join-Path $rootDir '.env' }
$fileValues = @{}
if (Test-Path -LiteralPath $envFile -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $value = $Matches[2].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) { $value = $value.Substring(1, $value.Length - 2) }
            else { $value = ($value -replace '\s+#.*$', '').TrimEnd() }
            $fileValues[$Matches[1]] = $value
        }
    }
}
$hostName = if ($env:GATEWAY_HOST) { $env:GATEWAY_HOST } elseif ($fileValues.ContainsKey('GATEWAY_HOST') -and $fileValues['GATEWAY_HOST']) { $fileValues['GATEWAY_HOST'] } else { '127.0.0.1' }
$port = if ($env:GATEWAY_PORT) { $env:GATEWAY_PORT } elseif ($fileValues.ContainsKey('GATEWAY_PORT') -and $fileValues['GATEWAY_PORT']) { $fileValues['GATEWAY_PORT'] } else { '3456' }
$localToken = if ($env:GATEWAY_API_KEY) { $env:GATEWAY_API_KEY } elseif ($fileValues.ContainsKey('GATEWAY_API_KEY')) { $fileValues['GATEWAY_API_KEY'] } else { '' }
if ($env:GATEWAY_BASE_URL) { $baseUrl = $env:GATEWAY_BASE_URL.TrimEnd('/') }
else {
    if ($hostName -in @('127.0.0.1', 'localhost', '::1', '[::1]')) { $connectHost = if ($hostName -eq '::1') { '[::1]' } else { $hostName } }
    else { $connectHost = '127.0.0.1' }
    $baseUrl = "http://${connectHost}:$port"
}
$claudeCommand = if ($env:CLAUDE_BIN) { $env:CLAUDE_BIN } else { 'claude' }

try {
    $health = Invoke-RestMethod -Method Get -Uri "$baseUrl/health" -TimeoutSec 2
    if ($health.status -ne 'ok') { throw 'Unexpected health response.' }
} catch {
    throw "Gateway health check failed at $baseUrl/health. Start it in a separate terminal: npm start (from tools/openai-compatible-claude-gateway). No process was stopped."
}

$command = Get-Command $claudeCommand -ErrorAction SilentlyContinue
if (-not $command -and -not (Test-Path -LiteralPath $claudeCommand -PathType Leaf)) {
    throw "Claude Code executable was not found. Set CLAUDE_BIN to its path or ensure 'claude' is on PATH."
}

# Save and restore the caller's process environment after the child exits. Never persist values to a profile.
$names = @(
    'ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_AUTO_MODE_SERVER',
    'CLAUDE_CODE_ATTRIBUTION_HEADER', 'CLAUDE_CODE_DISABLE_THINKING', 'CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS', 'CLAUDE_CODE_EFFORT_LEVEL',
    'OPENAI_COMPATIBLE_API_KEY', 'OPENAI_COMPATIBLE_BASE_URL', 'OPENAI_COMPATIBLE_MODEL',
    'OPENAI_COMPATIBLE_MODEL_MAP', 'OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH', 'OPENAI_COMPATIBLE_CAPABILITIES',
    'OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP', 'GATEWAY_API_KEY'
)
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:ANTHROPIC_BASE_URL = $baseUrl
    $env:CLAUDE_CODE_AUTO_MODE_SERVER = '0'
    $env:CLAUDE_CODE_ATTRIBUTION_HEADER = '0'
    $env:CLAUDE_CODE_DISABLE_THINKING = '1'
    if ([string]::IsNullOrEmpty($old['CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS'])) { $env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = '1' }
    if ([string]::IsNullOrEmpty($old['CLAUDE_CODE_EFFORT_LEVEL'])) { $env:CLAUDE_CODE_EFFORT_LEVEL = 'auto' }
    Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_MODEL_MAP -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_CAPABILITIES -ErrorAction SilentlyContinue
    Remove-Item Env:OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP -ErrorAction SilentlyContinue
    Remove-Item Env:GATEWAY_API_KEY -ErrorAction SilentlyContinue
    if ($localToken) { $env:ANTHROPIC_AUTH_TOKEN = $localToken }
    else { Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue }
    & $claudeCommand @ClaudeArgs
    exit $LASTEXITCODE
} finally {
    foreach ($name in $names) {
        if ($null -eq $old[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
    }
}
