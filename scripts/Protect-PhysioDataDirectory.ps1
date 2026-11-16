[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$UserAccount = "$env:USERDOMAIN\$env:USERNAME"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedDataPath = [IO.Path]::GetFullPath((Join-Path $projectRoot "data"))
$dataPath = (Resolve-Path -LiteralPath $expectedDataPath).Path.TrimEnd("\")
$aclBackupDirectory = Join-Path $projectRoot "security\acl-backups"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$administratorRole = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not $principal.IsInRole($administratorRole)) {
    throw "Run this script as Administrator."
}

if ($dataPath -ne $expectedDataPath.TrimEnd("\")) {
    throw "Only the project data directory is allowed: $expectedDataPath"
}

if (-not (Test-Path -LiteralPath $dataPath -PathType Container)) {
    throw "Data directory does not exist: $dataPath"
}

$targetDescription = "Restrict NTFS access to $UserAccount, SYSTEM, and Administrators"
if (-not $PSCmdlet.ShouldProcess($dataPath, $targetDescription)) {
    return
}

New-Item -ItemType Directory -Path $aclBackupDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$aclBackupPath = Join-Path $aclBackupDirectory "data-acl-$timestamp.xml"
Get-Acl -LiteralPath $dataPath | Export-Clixml -LiteralPath $aclBackupPath

& icacls.exe $dataPath /reset /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to reset the data directory ACL. Backup: $aclBackupPath"
}

& icacls.exe $dataPath /inheritance:r /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to disable ACL inheritance. Backup: $aclBackupPath"
}

& icacls.exe $dataPath /grant:r `
    "${UserAccount}:(OI)(CI)F" `
    "NT AUTHORITY\SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" `
    /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply the restricted ACL. Restore from: $aclBackupPath"
}

$acl = Get-Acl -LiteralPath $dataPath
$allowedIdentities = @(
    $UserAccount,
    "NT AUTHORITY\SYSTEM",
    "BUILTIN\Administrators"
)
$unexpectedRules = @(
    $acl.Access | Where-Object {
        $allowedIdentities -notcontains $_.IdentityReference.Value
    }
)
if ($unexpectedRules.Count -gt 0) {
    $names = $unexpectedRules.IdentityReference.Value -join ", "
    throw "ACL verification failed. Unexpected principals: $names"
}

Write-Host "Data directory access restricted: $dataPath"
Write-Host "Allowed: $UserAccount, SYSTEM, Administrators"
Write-Host "Original ACL backup: $aclBackupPath"
