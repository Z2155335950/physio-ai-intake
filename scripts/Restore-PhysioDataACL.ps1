[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$UserAccount,

    [Parameter(Mandatory = $true)]
    [string]$AgentAccount,

    [Parameter(Mandatory = $true)]
    [string]$ResultPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resolvedResultPath = [IO.Path]::GetFullPath($ResultPath)
trap {
    $message = $_ | Out-String
    try {
        $resultDirectory = Split-Path -Parent $resolvedResultPath
        New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
        [ordered]@{
            restored_at = (Get-Date).ToString("o")
            ok = $false
            error = $message.Trim()
        } | ConvertTo-Json -Depth 4 | Set-Content `
            -LiteralPath $resolvedResultPath `
            -Encoding UTF8
    }
    catch {
        # The original failure remains the useful diagnostic.
    }
    Write-Error $message
    exit 1
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$administratorRole = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not $principal.IsInRole($administratorRole)) {
    throw "Run this script from an elevated PowerShell process."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedDataPath = [IO.Path]::GetFullPath(
    (Join-Path $projectRoot "data")
).TrimEnd("\")
$dataPath = (Resolve-Path -LiteralPath $expectedDataPath).Path.TrimEnd("\")
if ($dataPath -ne $expectedDataPath) {
    throw "Only the project data directory is allowed: $expectedDataPath"
}
if (-not (Test-Path -LiteralPath $dataPath -PathType Container)) {
    throw "Data directory does not exist: $dataPath"
}

$projectPrefix = [IO.Path]::GetFullPath($projectRoot).TrimEnd("\") + "\"
if (-not $resolvedResultPath.StartsWith(
    $projectPrefix,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Result path must stay inside the project directory."
}

$aclBackupDirectory = Join-Path $projectRoot "security\acl-backups"
New-Item -ItemType Directory -Path $aclBackupDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$aclBackupPath = Join-Path $aclBackupDirectory "data-acl-$timestamp.xml"
Get-Acl -LiteralPath $dataPath | Export-Clixml -LiteralPath $aclBackupPath

$null = & takeown.exe /F $dataPath /A /R /D Y
if ($LASTEXITCODE -ne 0) {
    throw "Failed to take ownership of the data directory."
}

$null = & icacls.exe $dataPath /reset /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to reset the data directory ACL."
}

$null = & icacls.exe $dataPath /inheritance:r /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to disable ACL inheritance on the data directory."
}

$null = & icacls.exe $dataPath /grant:r `
    "${UserAccount}:(OI)(CI)F" `
    "${AgentAccount}:(OI)(CI)F" `
    "NT AUTHORITY\SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" `
    /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to grant the restricted data directory ACL."
}

$null = & icacls.exe $dataPath /setowner $UserAccount /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to set the data directory owner."
}

$items = @(
    Get-Item -LiteralPath $dataPath -Force
) + @(
    Get-ChildItem -LiteralPath $dataPath -Recurse -Force
)
$failures = New-Object System.Collections.Generic.List[string]
foreach ($item in $items) {
    try {
        $null = Get-Acl -LiteralPath $item.FullName
        if ($item.PSIsContainer) {
            $null = Get-ChildItem -LiteralPath $item.FullName -Force
        }
        else {
            $stream = [IO.File]::Open(
                $item.FullName,
                [IO.FileMode]::Open,
                [IO.FileAccess]::Read,
                [IO.FileShare]::ReadWrite
            )
            $stream.Dispose()
        }
    }
    catch {
        $failures.Add("$($item.FullName): $($_.Exception.Message)")
    }
}

$requiredFiles = @(
    (Join-Path $dataPath "knowledge_policy.json"),
    (Join-Path $dataPath "system_prompt.md"),
    (Join-Path $dataPath "customer_memory.sqlite3"),
    (Join-Path $dataPath "tool_audit.sqlite3")
)
foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        $failures.Add("${requiredFile}: required file is missing")
        continue
    }
    try {
        $stream = [IO.File]::Open(
            $requiredFile,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite
        )
        $stream.Dispose()
    }
    catch {
        $failures.Add("${requiredFile}: $($_.Exception.Message)")
    }
}

$resultDirectory = Split-Path -Parent $resolvedResultPath
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
$result = [ordered]@{
    restored_at = (Get-Date).ToString("o")
    data_path = $dataPath
    acl_backup = $aclBackupPath
    user_account = $UserAccount
    agent_account = $AgentAccount
    checked_items = $items.Count
    failures = @($failures)
    ok = $failures.Count -eq 0
}
$result | ConvertTo-Json -Depth 4 | Set-Content `
    -LiteralPath $resolvedResultPath `
    -Encoding UTF8

if ($failures.Count -gt 0) {
    throw "ACL restore completed with $($failures.Count) read failures."
}

Write-Host "Data directory ACL restored and verified: $dataPath"
Write-Host "Checked items: $($items.Count)"
Write-Host "ACL backup: $aclBackupPath"
