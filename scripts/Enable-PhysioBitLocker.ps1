[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RecoveryDirectory = "C:\Users\zhang\Documents\PhysioAssistant-Recovery"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$administratorRole = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not $principal.IsInRole($administratorRole)) {
    throw "Run this script as Administrator."
}

$edition = (Get-ItemProperty -LiteralPath `
    "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").EditionID
if ($edition -in @("Core", "CoreCountrySpecific", "CoreSingleLanguage")) {
    throw "Windows Home ($edition) does not support standard BitLocker. Upgrade to Pro, Enterprise, or Education first."
}

$tpm = Get-Tpm
if (-not $tpm.TpmPresent -or -not $tpm.TpmReady) {
    throw "TPM is not ready. Enable and initialize TPM in BIOS and Windows first."
}

$volumes = @("C:", "D:")
$existing = @{}
foreach ($mountPoint in $volumes) {
    if (-not (Get-Volume -DriveLetter $mountPoint.Substring(0, 1) `
        -ErrorAction SilentlyContinue)) {
        throw "Volume not found: $mountPoint"
    }
    $existing[$mountPoint] = Get-BitLockerVolume -MountPoint $mountPoint
}

function New-BitLockerRecoveryPassword {
    $groups = New-Object System.Collections.Generic.List[string]
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        for ($index = 0; $index -lt 8; $index++) {
            $bytes = New-Object byte[] 4
            $random.GetBytes($bytes)
            $value = [BitConverter]::ToUInt32($bytes, 0) % 1000000
            $groups.Add($value.ToString("D6"))
        }
    }
    finally {
        $random.Dispose()
    }
    return ($groups -join "-")
}

$message = "Create a recovery directory restricted to the current user, SYSTEM, and Administrators"
if (-not $PSCmdlet.ShouldProcess($RecoveryDirectory, $message)) {
    return
}

New-Item -ItemType Directory -Path $RecoveryDirectory -Force | Out-Null
$recoveryUser = "$env:USERDOMAIN\$env:USERNAME"
& icacls.exe $RecoveryDirectory /inheritance:r /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to disable ACL inheritance on the recovery directory."
}
& icacls.exe $RecoveryDirectory /grant:r `
    "${recoveryUser}:(OI)(CI)F" `
    "NT AUTHORITY\SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" `
    /T /C
if ($LASTEXITCODE -ne 0) {
    throw "Failed to restrict access to the recovery directory."
}

$plannedPasswords = @{}
$recoveryConfigured = @{}
foreach ($mountPoint in $volumes) {
    $existingRecovery = @(
        $existing[$mountPoint].KeyProtector | Where-Object {
            $_.KeyProtectorType -eq "RecoveryPassword"
        }
    ) | Select-Object -First 1
    if (
        $existing[$mountPoint].VolumeStatus -ne "FullyDecrypted" -and
        $existingRecovery -and
        $existingRecovery.RecoveryPassword
    ) {
        $plannedPasswords[$mountPoint] = $existingRecovery.RecoveryPassword
        $recoveryConfigured[$mountPoint] = $true
    }
    else {
        $plannedPasswords[$mountPoint] = New-BitLockerRecoveryPassword
        $recoveryConfigured[$mountPoint] = $false
    }
}

$recoveryFile = Join-Path $RecoveryDirectory `
    ("PhysioAssistant-BitLocker-{0}.txt" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$recoveryEntries = @(
    "Generated before encryption. Store these in a password manager or secure offline location.",
    "C: $($plannedPasswords["C:"])",
    "D: $($plannedPasswords["D:"])"
)
Set-Content -LiteralPath $recoveryFile `
    -Value $recoveryEntries `
    -Encoding UTF8
Write-Host "Recovery passwords saved before encryption to: $recoveryFile"

foreach ($mountPoint in $volumes) {
    $volume = $existing[$mountPoint]
    if ($volume.VolumeStatus -eq "FullyDecrypted") {
        $message = "Enable BitLocker on $mountPoint with XtsAes256 and used-space-only encryption"
        if (-not $PSCmdlet.ShouldProcess($mountPoint, $message)) {
            continue
        }
        if ($mountPoint -eq "C:") {
            Enable-BitLocker -MountPoint $mountPoint `
                -EncryptionMethod XtsAes256 `
                -UsedSpaceOnly `
                -RecoveryPassword $plannedPasswords[$mountPoint] `
                -RecoveryPasswordProtector `
                -SkipHardwareTest
        }
        else {
            Enable-BitLocker -MountPoint $mountPoint `
                -EncryptionMethod XtsAes256 `
                -UsedSpaceOnly `
                -RecoveryPassword $plannedPasswords[$mountPoint] `
                -RecoveryPasswordProtector `
                -SkipHardwareTest
        }
        $recoveryConfigured[$mountPoint] = $true
    }
}

foreach ($mountPoint in $volumes) {
    if (-not $recoveryConfigured[$mountPoint]) {
        $message = "Add a recovery-password protector to $mountPoint"
        if (-not $PSCmdlet.ShouldProcess($mountPoint, $message)) {
            continue
        }
        Add-BitLockerKeyProtector -MountPoint $mountPoint `
            -RecoveryPassword $plannedPasswords[$mountPoint] `
            -RecoveryPasswordProtector
        $recoveryConfigured[$mountPoint] = $true
    }
}

$systemVolume = Get-BitLockerVolume -MountPoint "C:"
$hasTpmProtector = @(
    $systemVolume.KeyProtector | Where-Object {
        $_.KeyProtectorType -eq "Tpm"
    }
).Count -gt 0
if (-not $hasTpmProtector) {
    $message = "Add a TPM protector to the system volume"
    if ($PSCmdlet.ShouldProcess("C:", $message)) {
        Add-BitLockerKeyProtector -MountPoint "C:" -TpmProtector
    }
}

if ((Get-BitLockerVolume -MountPoint "D:").ProtectionStatus -eq "On") {
    $message = "Enable automatic unlock for D: after the system volume unlocks"
    if ($PSCmdlet.ShouldProcess("D:", $message)) {
        Enable-BitLockerAutoUnlock -MountPoint "D:"
    }
}

$missingProtectors = @(
    $volumes | Where-Object { -not $recoveryConfigured[$_] }
)
if ($missingProtectors.Count -gt 0) {
    throw "Recovery-password protector missing on: $($missingProtectors -join ", "). Do not reboot; recovery passwords are in $recoveryFile"
}

Write-Host "BitLocker encryption started. Wait for every volume to reach 100%."
Write-Host "Copy recovery passwords to a trusted password manager or secure offline storage."
Get-BitLockerVolume -MountPoint $volumes |
    Select-Object MountPoint, VolumeStatus, ProtectionStatus, EncryptionPercentage |
    Format-Table -AutoSize
