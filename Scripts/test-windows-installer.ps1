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

    $result = Invoke-TestInstall 'ru' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "Russian install failed: $($result.Status)"
    foreach ($file in @($russian.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Russian output mismatch: $($file.path)"
    }

    $result = Invoke-TestInstall 'th' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "Thai switch failed: $($result.Status)"
    foreach ($file in @($thai.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "Thai output mismatch: $($file.path)"
    }
    $thaiOwnedAdditions = @($thai.files | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.originalSHA256) })
    Assert-True ($thaiOwnedAdditions.Count -gt 0) 'Thai payload did not exercise an owned helper file.'

    $result = Invoke-TestInstall 'de' $SteamRoot $GameRoot $StatusPath
    Assert-True ($result.ExitCode -eq 0 -and $result.Status.StartsWith("SUCCESS`n")) "German switch failed: $($result.Status)"
    foreach ($file in @($german.files)) {
        Assert-True ((Get-Sha256 (Join-Path $DataRoot ([string]$file.path))) -eq ([string]$file.payloadSHA256).ToLowerInvariant()) "German output mismatch: $($file.path)"
    }
    foreach ($file in $thaiOwnedAdditions) {
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $DataRoot ([string]$file.path)) -PathType Leaf)) "Retired Thai helper remains installed: $($file.path)"
    }

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
