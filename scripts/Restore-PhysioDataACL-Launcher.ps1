Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resultDirectory = Join-Path $PSScriptRoot "..\security\acl-backups"
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultPath = Join-Path $resultDirectory "data-acl-restore-$timestamp.json"
$logPath = Join-Path $resultDirectory "data-acl-restore-$timestamp.log"

try {
    & (Join-Path $PSScriptRoot "Restore-PhysioDataACL.ps1") `
        -UserAccount "LAPTOP-GK5LSAFJ\zhang" `
        -AgentAccount "LAPTOP-GK5LSAFJ\CodexSandboxOffline" `
        -ResultPath $resultPath *> $logPath
    "EXIT_CODE=$LASTEXITCODE" | Add-Content -LiteralPath $logPath -Encoding UTF8
    exit $LASTEXITCODE
}
catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
    "EXIT_CODE=1" | Add-Content -LiteralPath $logPath -Encoding UTF8
    exit 1
}
