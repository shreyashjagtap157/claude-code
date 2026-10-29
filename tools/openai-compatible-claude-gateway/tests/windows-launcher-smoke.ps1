$ErrorActionPreference = 'Stop'
$rootDir = Split-Path -Parent $PSScriptRoot
$wrapperPath = Join-Path $rootDir 'scripts/start-claude-with-openai-provider.ps1'
$healthPath = Join-Path $PSScriptRoot 'fixtures/fake-health-server.js'
$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($wrapperPath, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count -gt 0) { throw "PowerShell wrapper has parse errors: $($parseErrors.Message -join '; ')" }

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("gateway-ps-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$portFile = Join-Path $tempRoot 'health-port.txt'
$healthErrorFile = Join-Path $tempRoot 'health.stderr.txt'
$healthProcess = $null
try {
    $healthProcess = Start-Process -FilePath 'node' -ArgumentList @($healthPath) -PassThru -NoNewWindow -RedirectStandardOutput $portFile -RedirectStandardError $healthErrorFile
    $port = $null
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path -LiteralPath $portFile) {
            $rawPort = Get-Content -Raw -LiteralPath $portFile -ErrorAction SilentlyContinue
            if (-not [string]::IsNullOrWhiteSpace($rawPort)) {
                $candidate = $rawPort.Trim()
                if ($candidate -match '^\d+
        }
        if ($healthProcess.HasExited) {
            $details = if (Test-Path -LiteralPath $healthErrorFile) { Get-Content -Raw -LiteralPath $healthErrorFile } else { '' }
            throw "Fake health server exited unexpectedly. $details"
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $port) { throw 'Timed out waiting for fake health server startup.' }

    $fakeCliPath = Join-Path $tempRoot 'fake-claude.cmd'
    $fakeCli = @'
@echo off
if "%ANTHROPIC_BASE_URL%"=="http://127.0.0.1:PORT_PLACEHOLDER" (echo BASE=correct) else (echo BASE=wrong)
if "%ANTHROPIC_AUTH_TOKEN%"=="local-launch-token-fixture" (echo LOCAL_AUTH=correct) else (echo LOCAL_AUTH=wrong)
if "%CLAUDE_CODE_AUTO_MODE_SERVER%"=="0" (echo AUTO_MODE_SERVER=0) else (echo AUTO_MODE_SERVER=wrong)
if "%CLAUDE_CODE_ATTRIBUTION_HEADER%"=="0" (echo ATTRIBUTION=0) else (echo ATTRIBUTION=wrong)
if "%CLAUDE_CODE_DISABLE_THINKING%"=="1" (echo THINKING=disabled) else (echo THINKING=wrong)
if "%CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS%"=="1" (echo BETAS=disabled) else (echo BETAS=wrong)
if "%CLAUDE_CODE_EFFORT_LEVEL%"=="auto" (echo EFFORT=auto) else (echo EFFORT=wrong)
if "%OPENAI_COMPATIBLE_API_KEY%"=="" (echo UPSTREAM_KEY=absent) else (echo UPSTREAM_KEY=LEAKED)
if "%ANTHROPIC_API_KEY%"=="" (echo ANTHROPIC_API_KEY=absent) else (echo ANTHROPIC_API_KEY=LEAKED)
if "%GATEWAY_API_KEY%"=="" (echo GATEWAY_KEY=absent) else (echo GATEWAY_KEY=LEAKED)
exit /b 0
'@
    $fakeCli = $fakeCli.Replace('PORT_PLACEHOLDER', [string]$port)
    Set-Content -LiteralPath $fakeCliPath -Value $fakeCli -Encoding ascii

    $runnerPath = Join-Path $tempRoot 'launch-runner.ps1'
    $runner = @(
        "`$env:GATEWAY_BASE_URL = 'http://127.0.0.1:$port'",
        "`$env:GATEWAY_API_KEY = 'local-launch-token-fixture'",
        "`$env:OPENAI_COMPATIBLE_API_KEY = 'upstream-key-fixture-do-not-print'",
        "`$env:OPENAI_COMPATIBLE_BASE_URL = 'https://provider.example/v1'",
        "`$env:ANTHROPIC_API_KEY = 'old-anthropic-key-fixture-do-not-print'",
        "`$env:ANTHROPIC_AUTH_TOKEN = 'old-anthropic-token-fixture-do-not-print'",
        "`$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = ''",
        "`$env:CLAUDE_CODE_EFFORT_LEVEL = ''",
        "`$env:CLAUDE_BIN = '$fakeCliPath'",
        "& '$wrapperPath' -p 'gateway-launcher-contract-smoke'"
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $runnerPath -Value $runner -Encoding utf8

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $runnerPath 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "PowerShell launcher exited with code $exitCode. Output: $output" }
    $expected = @('BASE=correct', 'LOCAL_AUTH=correct', 'AUTO_MODE_SERVER=0', 'ATTRIBUTION=0', 'THINKING=disabled', 'BETAS=disabled', 'EFFORT=auto', 'UPSTREAM_KEY=absent', 'ANTHROPIC_API_KEY=absent', 'GATEWAY_KEY=absent')
    foreach ($value in $expected) {
        if (-not $output.Contains($value)) { throw "PowerShell launcher contract check failed at $value. Output: $output" }
    }
    if ($output -match 'LEAKED|old-anthropic-key-fixture-do-not-print|upstream-key-fixture-do-not-print') {
        throw "Credential-isolation assertion failed. Output: $output"
    }
    Write-Output 'PowerShell wrapper smoke passed: health check, child base URL, local token, Auto Mode selector, compatibility defaults, and upstream/local credential isolation.'
}
finally {
    if ($healthProcess -and -not $healthProcess.HasExited) { Stop-Process -Id $healthProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $tempRoot -Force -Recurse -ErrorAction SilentlyContinue
}
) { $port = [int]$candidate; break }
            }
        }
        if ($healthProcess.HasExited) {
            $details = if (Test-Path -LiteralPath $healthErrorFile) { Get-Content -Raw -LiteralPath $healthErrorFile } else { '' }
            throw "Fake health server exited unexpectedly. $details"
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $port) { throw 'Timed out waiting for fake health server startup.' }

    $fakeCliPath = Join-Path $tempRoot 'fake-claude.cmd'
    $fakeCli = @'
@echo off
if "%ANTHROPIC_BASE_URL%"=="http://127.0.0.1:PORT_PLACEHOLDER" (echo BASE=correct) else (echo BASE=wrong)
if "%ANTHROPIC_AUTH_TOKEN%"=="local-launch-token-fixture" (echo LOCAL_AUTH=correct) else (echo LOCAL_AUTH=wrong)
if "%CLAUDE_CODE_AUTO_MODE_SERVER%"=="0" (echo AUTO_MODE_SERVER=0) else (echo AUTO_MODE_SERVER=wrong)
if "%CLAUDE_CODE_ATTRIBUTION_HEADER%"=="0" (echo ATTRIBUTION=0) else (echo ATTRIBUTION=wrong)
if "%CLAUDE_CODE_DISABLE_THINKING%"=="1" (echo THINKING=disabled) else (echo THINKING=wrong)
if "%CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS%"=="1" (echo BETAS=disabled) else (echo BETAS=wrong)
if "%CLAUDE_CODE_EFFORT_LEVEL%"=="auto" (echo EFFORT=auto) else (echo EFFORT=wrong)
if "%OPENAI_COMPATIBLE_API_KEY%"=="" (echo UPSTREAM_KEY=absent) else (echo UPSTREAM_KEY=LEAKED)
if "%ANTHROPIC_API_KEY%"=="" (echo ANTHROPIC_API_KEY=absent) else (echo ANTHROPIC_API_KEY=LEAKED)
if "%GATEWAY_API_KEY%"=="" (echo GATEWAY_KEY=absent) else (echo GATEWAY_KEY=LEAKED)
exit /b 0
'@
    $fakeCli = $fakeCli.Replace('PORT_PLACEHOLDER', [string]$port)
    Set-Content -LiteralPath $fakeCliPath -Value $fakeCli -Encoding ascii

    $runnerPath = Join-Path $tempRoot 'launch-runner.ps1'
    $runner = @(
        "`$env:GATEWAY_BASE_URL = 'http://127.0.0.1:$port'",
        "`$env:GATEWAY_API_KEY = 'local-launch-token-fixture'",
        "`$env:OPENAI_COMPATIBLE_API_KEY = 'upstream-key-fixture-do-not-print'",
        "`$env:OPENAI_COMPATIBLE_BASE_URL = 'https://provider.example/v1'",
        "`$env:ANTHROPIC_API_KEY = 'old-anthropic-key-fixture-do-not-print'",
        "`$env:ANTHROPIC_AUTH_TOKEN = 'old-anthropic-token-fixture-do-not-print'",
        "`$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = ''",
        "`$env:CLAUDE_CODE_EFFORT_LEVEL = ''",
        "`$env:CLAUDE_BIN = '$fakeCliPath'",
        "& '$wrapperPath' -p 'gateway-launcher-contract-smoke'"
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $runnerPath -Value $runner -Encoding utf8

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $runnerPath 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "PowerShell launcher exited with code $exitCode. Output: $output" }
    $expected = @('BASE=correct', 'LOCAL_AUTH=correct', 'AUTO_MODE_SERVER=0', 'ATTRIBUTION=0', 'THINKING=disabled', 'BETAS=disabled', 'EFFORT=auto', 'UPSTREAM_KEY=absent', 'ANTHROPIC_API_KEY=absent', 'GATEWAY_KEY=absent')
    foreach ($value in $expected) {
        if (-not $output.Contains($value)) { throw "PowerShell launcher contract check failed at $value. Output: $output" }
    }
    if ($output -match 'LEAKED|old-anthropic-key-fixture-do-not-print|upstream-key-fixture-do-not-print') {
        throw "Credential-isolation assertion failed. Output: $output"
    }
    Write-Output 'PowerShell wrapper smoke passed: health check, child base URL, local token, Auto Mode selector, compatibility defaults, and upstream/local credential isolation.'
}
finally {
    if ($healthProcess -and -not $healthProcess.HasExited) { Stop-Process -Id $healthProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $tempRoot -Force -Recurse -ErrorAction SilentlyContinue
}
