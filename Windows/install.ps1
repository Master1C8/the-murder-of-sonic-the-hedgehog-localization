param(
    [Parameter(Mandatory = $true)][string]$BaseDirectory,
    [Parameter(Mandatory = $true)][string]$RuntimeCode,
    [Parameter(Mandatory = $true)][string]$StatusFile,
    [string]$GamePath,
    [string]$SteamRootOverride,
    [string]$StateRootOverride
)

$ErrorActionPreference = 'Stop'
$ExpectedAppId = '2324650'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Status([string]$Kind, [string]$Message) {
    [System.IO.File]::WriteAllText($StatusFile, "$Kind`n$Message", $Utf8NoBom)
}

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-VdfValue([string]$Text, [string]$Name) {
    $match = [regex]::Match($Text, '"' + [regex]::Escape($Name) + '"\s+"([^"]*)"', 'IgnoreCase')
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value
}

function Get-SafePath([string]$Root, [string]$Relative) {
    $normalized = $Relative.Replace('/', '\')
    if ([string]::IsNullOrWhiteSpace($normalized) -or [System.IO.Path]::IsPathRooted($normalized)) {
        throw "Unsafe path in the localization package: $Relative"
    }
    foreach ($part in $normalized.Split('\')) {
        if ([string]::IsNullOrEmpty($part) -or $part -eq '.' -or $part -eq '..') {
            throw "Unsafe path in the localization package: $Relative"
        }
    }
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $result = [System.IO.Path]::GetFullPath((Join-Path $rootFull $normalized))
    if (-not $result.StartsWith($rootFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path in the localization package: $Relative"
    }
    return $result
}

function Get-InstallationStateRoot($Installation, [string]$Override) {
    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        return [System.IO.Path]::GetFullPath($Override)
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Installation.GameRoot.ToLowerInvariant())
        $hash = $sha.ComputeHash($bytes)
    } finally {
        $sha.Dispose()
    }
    $installationId = -join ($hash[0..7] | ForEach-Object { $_.ToString('x2') })
    $localData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    if ([string]::IsNullOrWhiteSpace($localData)) { throw 'The local application data folder was not found.' }
    return Join-Path (Join-Path $localData 'VNR\2324650') $installationId
}

function Resolve-GameRoot([string]$InstallRoot) {
    $candidates = @($InstallRoot, (Join-Path $InstallRoot 'The Murder of Sonic The Hedgehog'))
    foreach ($candidate in $candidates) {
        $exe = Join-Path $candidate 'The Murder of Sonic The Hedgehog.exe'
        $data = Join-Path $candidate 'The Murder of Sonic The Hedgehog_Data'
        if ((Test-Path -LiteralPath $exe -PathType Leaf) -and (Test-Path -LiteralPath $data -PathType Container)) {
            return [pscustomobject]@{ GameRoot = $candidate; DataRoot = $data; Executable = $exe }
        }
    }
    return $null
}

function Get-SteamRoots([string]$Override) {
    $roots = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        $roots.Add(([System.IO.Path]::GetFullPath($Override)))
    }
    foreach ($entry in @(
        @{ Path = 'HKCU:\Software\Valve\Steam'; Name = 'SteamPath' },
        @{ Path = 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'; Name = 'InstallPath' },
        @{ Path = 'HKLM:\SOFTWARE\Valve\Steam'; Name = 'InstallPath' }
    )) {
        try {
            $value = (Get-ItemProperty -LiteralPath $entry.Path -Name $entry.Name -ErrorAction Stop).($entry.Name)
            if ($value) { $roots.Add(([System.IO.Path]::GetFullPath($value.Replace('/', '\')))) }
        } catch { }
    }
    foreach ($root in @($roots)) {
        $libraries = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (-not (Test-Path -LiteralPath $libraries -PathType Leaf)) { continue }
        $text = [System.IO.File]::ReadAllText($libraries)
        foreach ($match in [regex]::Matches($text, '"path"\s+"([^"]+)"', 'IgnoreCase')) {
            $roots.Add(([System.IO.Path]::GetFullPath($match.Groups[1].Value.Replace('\\', '\'))))
        }
    }
    return @($roots | Select-Object -Unique)
}

function Find-GameInstallation([string]$SelectedPath) {
    foreach ($steamRoot in Get-SteamRoots $SteamRootOverride) {
        $manifestPath = Join-Path $steamRoot "steamapps\appmanifest_$ExpectedAppId.acf"
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { continue }
        $manifestText = [System.IO.File]::ReadAllText($manifestPath)
        $appId = Get-VdfValue $manifestText 'appid'
        $installDir = Get-VdfValue $manifestText 'installdir'
        $buildId = Get-VdfValue $manifestText 'buildid'
        if ($appId -ne $ExpectedAppId -or [string]::IsNullOrWhiteSpace($installDir) -or [string]::IsNullOrWhiteSpace($buildId)) { continue }
        $installRoot = Join-Path $steamRoot ("steamapps\common\" + $installDir)
        $resolved = Resolve-GameRoot $installRoot
        if ($null -eq $resolved) { continue }
        if (-not [string]::IsNullOrWhiteSpace($SelectedPath)) {
            $selected = [System.IO.Path]::GetFullPath($SelectedPath).TrimEnd('\')
            $allowed = @(
                [System.IO.Path]::GetFullPath($installRoot).TrimEnd('\'),
                [System.IO.Path]::GetFullPath($resolved.GameRoot).TrimEnd('\'),
                [System.IO.Path]::GetFullPath($resolved.DataRoot).TrimEnd('\')
            )
            if (-not ($allowed | Where-Object { $_.Equals($selected, [System.StringComparison]::OrdinalIgnoreCase) })) { continue }
        }
        return [pscustomobject]@{
            SteamRoot = $steamRoot
            ManifestPath = $manifestPath
            BuildId = $buildId
            InstallRoot = $installRoot
            GameRoot = $resolved.GameRoot
            DataRoot = $resolved.DataRoot
            Executable = $resolved.Executable
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($SelectedPath)) {
        throw 'The selected folder is not the Steam installation registered for App ID 2324650.'
    }
    throw 'The Steam version of The Murder of Sonic the Hedgehog was not found.'
}

function Write-JsonFile($Value, [string]$Path) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 12) + "`n"), $Utf8NoBom)
}

function Read-Receipt([string]$Path, [string]$PackageId) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $receipt = [System.IO.File]::ReadAllText($Path) | ConvertFrom-Json
    if ([int]$receipt.schemaVersion -ne 1 -or [string]$receipt.packageID -ne $PackageId) {
        throw 'The previous VN Revival installation data could not be verified.'
    }
    return $receipt
}

function Recover-Transaction([string]$StateRoot, [string]$DataRoot, [string]$ReceiptPath) {
    $transaction = Join-Path $StateRoot 'transaction'
    if (-not (Test-Path -LiteralPath $transaction -PathType Container)) { return }
    $statePath = Join-Path $transaction 'state.json'
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        Remove-Item -LiteralPath $transaction -Recurse -Force
        return
    }
    $state = [System.IO.File]::ReadAllText($statePath) | ConvertFrom-Json
    if ([int]$state.schemaVersion -ne 1) { throw 'The interrupted installation record is malformed.' }
    if (-not [bool]$state.committed) {
        foreach ($file in @($state.files)) {
            $destination = Get-SafePath $DataRoot ([string]$file.path)
            $rollback = Get-SafePath (Join-Path $transaction 'rollback') ([string]$file.path)
            if (Test-Path -LiteralPath $rollback -PathType Leaf) {
                New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                Copy-Item -LiteralPath $rollback -Destination $destination -Force
            } elseif (-not [bool]$file.originalExisted -and (Test-Path -LiteralPath $destination -PathType Leaf)) {
                Remove-Item -LiteralPath $destination -Force
            }
        }
        $previousReceipt = Join-Path $transaction 'previous-receipt.json'
        if ([bool]$state.previousReceiptExisted) {
            if (-not (Test-Path -LiteralPath $previousReceipt -PathType Leaf)) {
                throw 'The interrupted installation is missing its previous receipt.'
            }
            Copy-Item -LiteralPath $previousReceipt -Destination $ReceiptPath -Force
        } elseif (Test-Path -LiteralPath $ReceiptPath -PathType Leaf) {
            Remove-Item -LiteralPath $ReceiptPath -Force
        }
    }
    Remove-Item -LiteralPath $transaction -Recurse -Force
}

function Migrate-SmokeTest($Installation, [string]$StateRoot, [string]$ReceiptPath, $SelectedFiles, [string]$PackageId) {
    if (Test-Path -LiteralPath $ReceiptPath -PathType Leaf) { return }
    $legacyRoot = Join-Path $Installation.GameRoot '.vn-revival\windows-smoke-test'
    $legacyReceiptPath = Join-Path $legacyRoot 'receipt.json'
    if (-not (Test-Path -LiteralPath $legacyReceiptPath -PathType Leaf)) { return }
    $legacy = [System.IO.File]::ReadAllText($legacyReceiptPath) | ConvertFrom-Json
    $expected = @($SelectedFiles | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.originalSHA256) })
    if ([string]$legacy.kind -ne 'windows-russian-runtime-smoke-test' -or
        [string]$legacy.steamAppId -ne $ExpectedAppId -or
        [string]$legacy.steamBuildId -ne '20535215' -or
        @($legacy.files).Count -ne $expected.Count) {
        throw 'The previous Windows test installation data could not be verified.'
    }
    $backupRoot = Join-Path $StateRoot 'original-backup'
    $legacyBackupRoot = Join-Path $legacyRoot 'original-backup'
    $migrated = @()
    foreach ($item in $expected) {
        $relative = [string]$item.path
        $legacyFile = @($legacy.files | Where-Object { [string]$_.path -eq $relative })
        if ($legacyFile.Count -ne 1 -or
            ([string]$legacyFile[0].originalSha256).ToLowerInvariant() -ne ([string]$item.originalSHA256).ToLowerInvariant()) {
            throw "The previous Windows test receipt does not match: $relative"
        }
        $destination = Get-SafePath $Installation.DataRoot $relative
        $legacyBackup = Get-SafePath $legacyBackupRoot $relative
        $installedHash = ([string]$legacyFile[0].patchedSha256).ToLowerInvariant()
        if ((Get-Sha256 $destination) -ne $installedHash -or
            (Get-Sha256 $legacyBackup) -ne ([string]$item.originalSHA256).ToLowerInvariant()) {
            throw "The previous Windows test installation was modified: $relative"
        }
        $backup = Get-SafePath $backupRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
        if (Test-Path -LiteralPath $backup -PathType Leaf) {
            if ((Get-Sha256 $backup) -ne ([string]$item.originalSHA256).ToLowerInvariant()) {
                throw "The original-file backup is damaged: $relative"
            }
        } else {
            Copy-Item -LiteralPath $legacyBackup -Destination $backup
        }
        $migrated += [pscustomobject]@{
            path = $relative
            originalExisted = $true
            originalSHA256 = ([string]$item.originalSHA256).ToLowerInvariant()
            installedSHA256 = $installedHash
        }
    }
    $receipt = [pscustomobject]@{
        schemaVersion = 1
        packageID = $PackageId
        steamBuildID = $Installation.BuildId
        installedAt = [DateTime]::UtcNow.ToString('o')
        activeLanguage = [pscustomobject]@{ siteLocale = 'ru'; runtimeCode = 'ru' }
        files = $migrated
    }
    Write-JsonFile $receipt $ReceiptPath
}

function Validate-Artifact([string]$PayloadRoot, $Artifact, [string]$Owner) {
    $path = Get-SafePath $PayloadRoot ([string]$Artifact.path)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "A payload file is missing: $Owner" }
    if ((Get-Sha256 $path) -ne ([string]$Artifact.sha256).ToLowerInvariant()) {
        throw "A payload checksum does not match: $Owner"
    }
    return $path
}

function Stage-PayloadFile($Item, [string]$PayloadRoot, [string]$BackupRoot, [string]$Output, [string]$Transaction) {
    $artifacts = @($Item.artifacts)
    if ($null -eq $Item.artifacts -or $artifacts.Count -eq 0) {
        $payloadRelative = if ([string]::IsNullOrWhiteSpace([string]$Item.payloadPath)) { [string]$Item.path } else { [string]$Item.payloadPath }
        $source = Get-SafePath $PayloadRoot $payloadRelative
        Copy-Item -LiteralPath $source -Destination $Output
        return
    }
    $tool = Join-Path $PayloadRoot 'Tools\xdelta3.exe'
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw 'The xdelta3 payload tool is missing.' }
    $source = Get-SafePath $BackupRoot ([string]$Item.path)
    $intermediates = @()
    try {
        for ($index = 0; $index -lt $artifacts.Count; $index++) {
            $patch = Get-SafePath $PayloadRoot ([string]$artifacts[$index].path)
            if ($index -eq $artifacts.Count - 1) {
                $target = $Output
            } else {
                $target = Join-Path $Transaction ("delta-" + [guid]::NewGuid().ToString('N'))
                $intermediates += $target
            }
            & $tool -d -f -s $source $patch $target | Out-Null
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $target -PathType Leaf)) {
                throw "The localized file could not be reconstructed: $($Item.path)"
            }
            $source = $target
        }
    } finally {
        foreach ($path in $intermediates) { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue }
    }
}

try {
    Write-Status 'WORKING' 'Finding the Steam installation…'
    $configPath = Join-Path $BaseDirectory 'Resources\PackageConfig.json'
    $payloadRoot = Join-Path $BaseDirectory 'Resources\LocalizationPayload'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw 'PackageConfig.json is missing.' }
    $config = [System.IO.File]::ReadAllText($configPath) | ConvertFrom-Json
    if ([int]$config.schemaVersion -ne 2 -or [string]$config.steamAppID -ne $ExpectedAppId) {
        throw 'The localization package configuration is invalid.'
    }
    if (-not [bool]$config.payloadReady -or @($config.languages).Count -ne 30) {
        throw 'The complete 30-language package is not included in this installer.'
    }
    $selected = @($config.languages | Where-Object { [string]$_.runtimeCode -eq $RuntimeCode })
    if ($selected.Count -ne 1 -or -not [bool]$selected[0].ready) {
        throw "The selected language is not ready: $RuntimeCode"
    }
    $selected = $selected[0]
    $selectedFiles = @($selected.files)
    if ($selectedFiles.Count -eq 0) { throw 'The selected language payload is empty.' }

    $installation = Find-GameInstallation $GamePath
    $running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($installation.GameRoot + '\', [System.StringComparison]::OrdinalIgnoreCase) }
        catch { $false }
    }
    if ($running) { throw 'The game is running. Close it before installing a localization.' }

    Write-Status 'WORKING' 'Verifying the localization package…'
    $tool = Join-Path $payloadRoot 'Tools\xdelta3.exe'
    $buildManifestPath = Join-Path $payloadRoot 'BuildManifest.json'
    if (-not (Test-Path -LiteralPath $buildManifestPath -PathType Leaf)) { throw 'The payload build manifest is missing.' }
    $buildManifest = [System.IO.File]::ReadAllText($buildManifestPath) | ConvertFrom-Json
    if ((Get-Sha256 $tool) -ne ([string]$buildManifest.deltaTool.sha256).ToLowerInvariant()) {
        throw 'The xdelta3 payload tool failed its integrity check.'
    }
    foreach ($item in $selectedFiles) {
        if ($null -ne $item.artifacts) {
            foreach ($artifact in @($item.artifacts)) { [void](Validate-Artifact $payloadRoot $artifact ([string]$item.path)) }
        } else {
            $payloadRelative = if ([string]::IsNullOrWhiteSpace([string]$item.payloadPath)) { [string]$item.path } else { [string]$item.payloadPath }
            $artifact = [pscustomobject]@{ path = $payloadRelative; sha256 = [string]$item.artifactSHA256 }
            [void](Validate-Artifact $payloadRoot $artifact ([string]$item.path))
        }
    }

    $stateRoot = Get-InstallationStateRoot $installation $StateRootOverride
    $backupRoot = Join-Path $stateRoot 'original-backup'
    $receiptPath = Join-Path $stateRoot 'receipt.json'
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    Recover-Transaction $stateRoot $installation.DataRoot $receiptPath
    Migrate-SmokeTest $installation $stateRoot $receiptPath $selectedFiles ([string]$config.packageID)
    $previousReceipt = Read-Receipt $receiptPath ([string]$config.packageID)
    $steamBuildChanged = if ($null -ne $previousReceipt) {
        [string]$previousReceipt.steamBuildID -ne [string]$installation.BuildId
    } else {
        [string]$installation.BuildId -ne [string]$config.steamBuildID
    }

    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $receiptFiles = @()
    foreach ($item in $selectedFiles) {
        $relative = [string]$item.path
        $destination = Get-SafePath $installation.DataRoot $relative
        $originalHash = if ([string]::IsNullOrWhiteSpace([string]$item.originalSHA256)) { $null } else { ([string]$item.originalSHA256).ToLowerInvariant() }
        $payloadHash = ([string]$item.payloadSHA256).ToLowerInvariant()
        $currentHash = Get-Sha256 $destination
        $prior = @()
        if ($null -ne $previousReceipt) { $prior = @($previousReceipt.files | Where-Object { [string]$_.path -eq $relative }) }
        if ($prior.Count -gt 1) { throw "The previous receipt contains a duplicate path: $relative" }
        if ($prior.Count -eq 1) {
            $restoredOriginal = $null -ne $originalHash -and $currentHash -eq $originalHash
            $missingOwnedAddition = $null -eq $currentHash -and -not [bool]$prior[0].originalExisted -and $null -eq $originalHash
            if ($currentHash -ne ([string]$prior[0].installedSHA256).ToLowerInvariant() -and
                $currentHash -ne $payloadHash -and -not $restoredOriginal -and -not $missingOwnedAddition) {
                if ($steamBuildChanged) { throw "Steam build $($installation.BuildId) changed a required game file: $relative" }
                throw "The file was modified by another patch: $relative"
            }
        } elseif ($null -ne $originalHash) {
            if ($null -eq $currentHash) { throw "A required game file is missing: $relative" }
            if ($currentHash -ne $originalHash) {
                if ($steamBuildChanged) { throw "Steam build $($installation.BuildId) changed a required game file: $relative" }
                throw "The game file version is unsupported: $relative"
            }
        } elseif ($null -ne $currentHash) {
            throw "The file belongs to another patch: $relative"
        }
        if ($null -ne $originalHash) {
            $backup = Get-SafePath $backupRoot $relative
            if (Test-Path -LiteralPath $backup -PathType Leaf) {
                if ((Get-Sha256 $backup) -ne $originalHash) { throw "The original-file backup is damaged: $relative" }
            } else {
                if ($currentHash -ne $originalHash) { throw "The original-file backup is unavailable: $relative" }
                New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
                Copy-Item -LiteralPath $destination -Destination $backup
                if ((Get-Sha256 $backup) -ne $originalHash) { throw "The original-file backup could not be verified: $relative" }
            }
        }
        $receiptFiles += [pscustomobject]@{
            path = $relative
            originalExisted = ($null -ne $originalHash)
            originalSHA256 = $originalHash
            installedSHA256 = $payloadHash
        }
    }

    $activePaths = @{}
    foreach ($item in $selectedFiles) { $activePaths[[string]$item.path] = $true }
    $retiredFiles = @()
    if ($null -ne $previousReceipt) {
        $retiredFiles = @($previousReceipt.files | Where-Object { -not $activePaths.ContainsKey([string]$_.path) })
    }
    foreach ($prior in $retiredFiles) {
        $relative = [string]$prior.path
        $destination = Get-SafePath $installation.DataRoot $relative
        $currentHash = Get-Sha256 $destination
        if ($null -ne $currentHash -and $currentHash -ne ([string]$prior.installedSHA256).ToLowerInvariant()) {
            throw "A retired localization file was modified by another patch: $relative"
        }
        if ($null -eq $currentHash -and [bool]$prior.originalExisted) {
            throw "A previously owned game file is missing: $relative"
        }
        if ([bool]$prior.originalExisted) {
            $backup = Get-SafePath $backupRoot $relative
            if ((Get-Sha256 $backup) -ne ([string]$prior.originalSHA256).ToLowerInvariant()) {
                throw "The original-file backup is damaged: $relative"
            }
        }
    }

    Write-Status 'WORKING' 'Reconstructing the selected language…'
    $transaction = Join-Path $stateRoot 'transaction'
    if (Test-Path -LiteralPath $transaction) { Remove-Item -LiteralPath $transaction -Recurse -Force }
    $rollbackRoot = Join-Path $transaction 'rollback'
    $stageRoot = Join-Path $transaction 'staged'
    New-Item -ItemType Directory -Path $rollbackRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
    $transactionFiles = @($receiptFiles) + @($retiredFiles)
    foreach ($file in $transactionFiles) {
        $destination = Get-SafePath $installation.DataRoot ([string]$file.path)
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            $rollback = Get-SafePath $rollbackRoot ([string]$file.path)
            New-Item -ItemType Directory -Path (Split-Path -Parent $rollback) -Force | Out-Null
            Copy-Item -LiteralPath $destination -Destination $rollback
        }
    }
    $previousReceiptExisted = Test-Path -LiteralPath $receiptPath -PathType Leaf
    if ($previousReceiptExisted) { Copy-Item -LiteralPath $receiptPath -Destination (Join-Path $transaction 'previous-receipt.json') }
    foreach ($item in $selectedFiles) {
        $stage = Get-SafePath $stageRoot ([string]$item.path)
        New-Item -ItemType Directory -Path (Split-Path -Parent $stage) -Force | Out-Null
        Stage-PayloadFile $item $payloadRoot $backupRoot $stage $transaction
        if ((Get-Sha256 $stage) -ne ([string]$item.payloadSHA256).ToLowerInvariant()) {
            throw "The reconstructed file checksum does not match: $($item.path)"
        }
    }
    $state = [pscustomobject]@{
        schemaVersion = 1
        packageID = [string]$config.packageID
        committed = $false
        previousReceiptExisted = [bool]$previousReceiptExisted
        files = $transactionFiles
    }
    Write-JsonFile $state (Join-Path $transaction 'state.json')

    try {
        Write-Status 'WORKING' 'Installing the selected language…'
        foreach ($item in $selectedFiles) {
            $destination = Get-SafePath $installation.DataRoot ([string]$item.path)
            $stage = Get-SafePath $stageRoot ([string]$item.path)
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Move-Item -LiteralPath $stage -Destination $destination -Force
            if ((Get-Sha256 $destination) -ne ([string]$item.payloadSHA256).ToLowerInvariant()) {
                throw "Installed-file verification failed: $($item.path)"
            }
        }
        foreach ($prior in $retiredFiles) {
            $destination = Get-SafePath $installation.DataRoot ([string]$prior.path)
            if ([bool]$prior.originalExisted) {
                Copy-Item -LiteralPath (Get-SafePath $backupRoot ([string]$prior.path)) -Destination $destination -Force
            } elseif (Test-Path -LiteralPath $destination -PathType Leaf) {
                Remove-Item -LiteralPath $destination -Force
            }
        }
        $receipt = [pscustomobject]@{
            schemaVersion = 1
            packageID = [string]$config.packageID
            steamBuildID = [string]$installation.BuildId
            installedAt = [DateTime]::UtcNow.ToString('o')
            activeLanguage = [pscustomobject]@{
                siteLocale = [string]$selected.siteLocale
                runtimeCode = [string]$selected.runtimeCode
            }
            files = $receiptFiles
        }
        Write-JsonFile $receipt $receiptPath
        $state.committed = $true
        Write-JsonFile $state (Join-Path $transaction 'state.json')
        Remove-Item -LiteralPath $transaction -Recurse -Force
    } catch {
        Recover-Transaction $stateRoot $installation.DataRoot $receiptPath
        throw
    }

    Write-Status 'SUCCESS' $installation.GameRoot
    exit 0
} catch {
    try { Write-Status 'ERROR' $_.Exception.Message } catch { }
    exit 1
}
