param(
    [Parameter(Mandatory = $true)][string]$ReleaseRoot,
    [Parameter(Mandatory = $true)][string]$FixtureDataRoot,
    [string]$InstallerPath
)

$ErrorActionPreference = 'Stop'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Installer = if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
    Join-Path $ReleaseRoot 'Resources\install.ps1'
} else {
    [System.IO.Path]::GetFullPath($InstallerPath)
}
$ConfigPath = Join-Path $ReleaseRoot 'Resources\PackageConfig.json'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Invoke-TestInstall(
    [string]$RuntimeCode,
    [string]$SteamRoot,
    [string]$GameRoot,
    [string]$StatusPath
) {
    Remove-Item -LiteralPath $StatusPath -Force -ErrorAction SilentlyContinue
    $arguments = @(
        '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', $Installer,
        '-BaseDirectory', $ReleaseRoot,
        '-RuntimeCode', $RuntimeCode,
        '-StatusFile', $StatusPath,
        '-GamePath', $GameRoot,
        '-SteamRootOverride', $SteamRoot,
        '-StateRootOverride', (Join-Path $TestRoot 's')
    )
    & powershell.exe @arguments
    $exitCode = $LASTEXITCODE
    Assert-True (Test-Path -LiteralPath $StatusPath -PathType Leaf) 'The installer did not write a status file.'
    return [pscustomobject]@{
        ExitCode = $exitCode
        Status = [System.IO.File]::ReadAllText($StatusPath)
    }
}

Assert-True (Test-Path -LiteralPath $Installer -PathType Leaf) "Installer script is missing: $Installer"
Assert-True (Test-Path -LiteralPath $ConfigPath -PathType Leaf) "Package config is missing: $ConfigPath"
$config = [System.IO.File]::ReadAllText($ConfigPath) | ConvertFrom-Json
$russian = @($config.languages | Where-Object { $_.runtimeCode -eq 'ru' })[0]
$thai = @($config.languages | Where-Object { $_.runtimeCode -eq 'th' })[0]
$german = @($config.languages | Where-Object { $_.runtimeCode -eq 'de' })[0]
Assert-True ($null -ne $russian -and $null -ne $thai -and $null -ne $german) 'Required test locales are missing.'
$sharedFiles = @($config.files)
Assert-True ($sharedFiles.Count -gt 60) 'The shared payload is missing.'
$russian.files = @($sharedFiles + @($russian.files))
$thai.files = @($sharedFiles + @($thai.files))
$german.files = @($sharedFiles + @($german.files))
$buildManifest = [System.IO.File]::ReadAllText((Join-Path $ReleaseRoot 'Resources\LocalizationPayload\BuildManifest.json')) | ConvertFrom-Json
Assert-True ([string]$buildManifest.architecture -eq 'shared-runtime-external-locale-data') 'The compact shared-runtime payload is not installed.'
$localePacks = @($russian.files | Where-Object { [string]$_.path -like 'StreamingAssets/VNRevival/Locales/*' })
Assert-True ($localePacks.Count -eq 60) 'The payload does not contain both runtime and story packs for all 30 locales.'

$TestRoot = 'C:\vnr-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$SteamRoot = Join-Path $TestRoot 'Steam'
$SteamApps = Join-Path $SteamRoot 'steamapps'
$InstallRoot = Join-Path $SteamApps 'common\Themurderofsonicthehedgehog'
$GameRoot = Join-Path $InstallRoot 'The Murder of Sonic The Hedgehog'
$DataRoot = Join-Path $GameRoot 'The Murder of Sonic The Hedgehog_Data'
$StatusPath = Join-Path $TestRoot 'status.txt'

try {
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    [System.IO.File]::WriteAllBytes((Join-Path $GameRoot 'The Murder of Sonic The Hedgehog.exe'), [byte[]](0))
    $manifest = @"
"AppState"
{
    "appid" "2324650"
    "installdir" "Themurderofsonicthehedgehog"
    "buildid" "20535215"
}
"@
    New-Item -ItemType Directory -Path $SteamApps -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $SteamApps 'appmanifest_2324650.acf'), $manifest, $Utf8NoBom)

    foreach ($file in @($russian.files | Where-Object { $null -ne $_.originalSHA256 })) {
        $source = Join-Path $FixtureDataRoot ([string]$file.path)
        $destination = Join-Path $DataRoot ([string]$file.path)
        Assert-True ((Get-Sha256 $source) -eq ([string]$file.originalSHA256).ToLowerInvariant()) "Fixture hash mismatch: $($file.path)"
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }

    # Exercise migration from the earlier Russian smoke-test layout. The new
    # installer must transactionally restore legacy-owned originals, remove a
    # legacy helper, and then apply the compact shared runtime.
    $legacyRoot = Join-Path $GameRoot '.vn-revival\windows-smoke-test'
    $legacyBackupRoot = Join-Path $legacyRoot 'original-backup'
    $assemblyRelative = 'Managed/Assembly-CSharp.dll'
    $assemblyPath = Join-Path $DataRoot $assemblyRelative
    $assemblyBackup = Join-Path $legacyBackupRoot $assemblyRelative
    New-Item -ItemType Directory -Path (Split-Path -Parent $assemblyBackup) -Force | Out-Null
    Copy-Item -LiteralPath $assemblyPath -Destination $assemblyBackup
    $assemblyOriginalHash = Get-Sha256 $assemblyPath
    [System.IO.File]::AppendAllText($assemblyPath, 'legacy smoke patch', $Utf8NoBom)
    $legacyHelperRelative = 'Managed/VNRevival.TextShaper.dll'
    $legacyHelperPath = Join-Path $DataRoot $legacyHelperRelative
    [System.IO.File]::WriteAllText($legacyHelperPath, 'legacy helper', $Utf8NoBom)
    $legacyReceipt = [pscustomobject]@{
        kind = 'windows-russian-runtime-smoke-test'
        steamAppId = '2324650'
        steamBuildId = '20535215'
        files = @(
            [pscustomobject]@{
                path = $assemblyRelative
                originalSha256 = $assemblyOriginalHash
                patchedSha256 = Get-Sha256 $assemblyPath
            },
            [pscustomobject]@{
                path = $legacyHelperRelative
                originalSha256 = $null
                patchedSha256 = Get-Sha256 $legacyHelperPath
            }
        )
    }
    New-Item -ItemType Directory -Path $legacyRoot -Force | Out-Null
    [System.IO.File]::WriteAllText(
        (Join-Path $legacyRoot 'receipt.json'),
        (($legacyReceipt | ConvertTo-Json -Depth 8) + "`n"),
        $Utf8NoBom
    )

    $result = Invoke-TestInstall 'ru' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "Russian install failed: $($result.Status)"
    Assert-True (-not (Test-Path -LiteralPath $legacyHelperPath -PathType Leaf)) 'The retired legacy text-shaper helper was not removed.'
    foreach ($file in @($russian.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Russian output mismatch: $($file.path)"
    }

    $result = Invoke-TestInstall 'th' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "Thai switch failed: $($result.Status)"
    foreach ($file in @($thai.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Thai output mismatch: $($file.path)"
    }
    $sharedAdditions = @($thai.files | Where-Object {
        [string]::IsNullOrWhiteSpace([string]$_.originalSHA256) -and
        [string]$_.path -ne 'StreamingAssets/VNRevival/active-locale.txt'
    })
    Assert-True ($sharedAdditions.Count -gt 60) 'The complete shared locale payload was not installed.'

    $result = Invoke-TestInstall 'de' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "German switch failed: $($result.Status)"
    foreach ($file in @($german.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "German output mismatch: $($file.path)"
    }
    foreach ($file in $sharedAdditions) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Shared payload changed during language switch: $($file.path)"
    }
    Assert-True ([System.IO.File]::ReadAllText((Join-Path $DataRoot 'StreamingAssets\VNRevival\active-locale.txt')).Trim() -eq 'de') 'The active locale did not switch to German.'

    foreach ($file in @($russian.files | Where-Object { $null -ne $_.originalSHA256 })) {
        Copy-Item -LiteralPath (Join-Path $FixtureDataRoot ([string]$file.path)) -Destination (Join-Path $DataRoot ([string]$file.path)) -Force
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $SteamApps 'appmanifest_2324650.acf'),
        $manifest.Replace('"20535215"', '"99999999"'),
        $Utf8NoBom
    )
    $result = Invoke-TestInstall 'ru' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "Post-update reinstall failed: $($result.Status)"
    foreach ($file in @($russian.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Post-update Russian output mismatch: $($file.path)"
    }
    $receiptPath = Join-Path $TestRoot 's\receipt.json'
    $receipt = [System.IO.File]::ReadAllText($receiptPath) | ConvertFrom-Json
    Assert-True ([string]$receipt.steamBuildID -eq '99999999') 'The post-update receipt did not record the newer Steam build.'

    $protected = Join-Path $DataRoot ([string]$russian.files[0].path)
    [System.IO.File]::AppendAllText($protected, 'foreign modification', $Utf8NoBom)
    $foreignHash = Get-Sha256 $protected
    $result = Invoke-TestInstall 'de' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -ne 0 -and $result.Status.StartsWith("ERROR`n")) 'Foreign modification was not rejected.'
    Assert-True ((Get-Sha256 $protected) -eq $foreignHash) 'Foreign modification changed after installer refusal.'

    Write-Output 'WINDOWS_INSTALLER_FAKE_FOLDER_TEST_PASS'
} finally {
    Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
