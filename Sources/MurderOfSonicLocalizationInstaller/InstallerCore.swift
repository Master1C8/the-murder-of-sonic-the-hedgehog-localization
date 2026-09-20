import CryptoKit
import Foundation

struct GameInstallation: Equatable, Sendable {
    let root: URL
    let appBundle: URL
    let dataDirectory: URL
    let steamAppID: String
    let steamBuildID: String
    let steamManifest: URL
}

struct SteamManifest: Equatable, Sendable {
    let appID: String
    let installDirectory: String
    let buildID: String
    let url: URL
}

struct ReceiptFile: Codable, Equatable, Sendable {
    let path: String
    let originalExisted: Bool
    let originalSHA256: String?
    let installedSHA256: String
}

struct InstallationReceipt: Codable, Equatable, Sendable {
    let schemaVersion: Int
    let packageID: String
    let steamBuildID: String
    let installedAt: Date
    let activeLanguage: ActiveLanguageSelection?
    let files: [ReceiptFile]
}

struct TransactionState: Codable, Equatable, Sendable {
    let schemaVersion: Int
    let packageID: String
    var committed: Bool
    let previousReceiptExisted: Bool?
    let files: [ReceiptFile]
}

private struct LegacyDevelopmentReceipt: Decodable {
    let kind: String
    let steamAppId: String
    let steamBuildId: String
    let targetLocale: String
    let files: [LegacyDevelopmentReceiptFile]
}

private struct LegacyDevelopmentReceiptFile: Decodable {
    let path: String
    let originalSha256: String
    let patchedSha256: String
}

enum InstallerError: LocalizedError {
    case invalidGameFolder
    case steamManifestMissing
    case wrongSteamApp(String)
    case unsupportedSteamBuild(expected: String, actual: String)
    case payloadNotReady
    case invalidLanguageSelection(String)
    case missingPayloadFile(String)
    case payloadChecksumMismatch(String)
    case unsupportedGameFile(String)
    case missingOriginalFile(String)
    case foreignModification(String)
    case damagedBackup(String)
    case unsafePath(String)
    case malformedReceipt
    case deltaToolMissing
    case deltaApplicationFailed(String)

    var errorDescription: String? {
        switch self {
        case .invalidGameFolder:
            "Steam-версия The Murder of Sonic the Hedgehog не найдена в выбранной папке."
        case .steamManifestMissing:
            "Не найден Steam-манифест игры appmanifest_2324650.acf."
        case .wrongSteamApp(let value):
            "Выбрана другая Steam-игра (App ID \(value))."
        case .unsupportedSteamBuild(let expected, let actual):
            "Сборка Steam \(actual) не поддерживается. Ожидается сборка \(expected)."
        case .payloadNotReady:
            "Полный пакет из 30 языков ещё не добавлен в эту сборку установщика."
        case .invalidLanguageSelection(let value):
            "Выбранный язык не входит в готовый пакет локализаций: \(value)."
        case .missingPayloadFile(let path):
            "В приложении отсутствует файл языкового мультипатча: \(path)."
        case .payloadChecksumMismatch(let path):
            "Контрольная сумма языкового мультипатча не совпала: \(path)."
        case .unsupportedGameFile(let path):
            "Версия игрового файла не поддерживается: \(path). Обновите игру в Steam."
        case .missingOriginalFile(let path):
            "В установленной игре отсутствует обязательный файл: \(path)."
        case .foreignModification(let path):
            "Файл \(path) уже изменён другим патчем. Установщик не будет его перезаписывать."
        case .damagedBackup(let path):
            "Резервная копия оригинального файла повреждена: \(path)."
        case .unsafePath(let path):
            "Небезопасный путь в пакете: \(path)."
        case .malformedReceipt:
            "Не удалось проверить данные предыдущей установки VN Revival."
        case .deltaToolMissing:
            "В приложении отсутствует инструмент применения языковых дельт."
        case .deltaApplicationFailed(let path):
            "Не удалось восстановить локализованный файл из проверенной дельты: \(path)."
        }
    }
}

struct InstallerCore {
    static let appName = "The Murder of Sonic The Hedgehog.app"
    static let executableName = "The Murder of Sonic The Hedgehog"
    static let dataRelativePath = "Contents/Resources/Data"

    let fileManager: FileManager

    init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
    }

    func detectSteamInstallation(
        appID: String,
        steamRoot: URL? = nil
    ) -> GameInstallation? {
        let root = steamRoot ?? fileManager.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/Steam",
            isDirectory: true
        )
        for library in steamLibraryRoots(steamRoot: root) {
            let steamApps = library.appendingPathComponent("steamapps", isDirectory: true)
            let manifestURL = steamApps.appendingPathComponent("appmanifest_\(appID).acf")
            guard let manifest = loadSteamManifest(manifestURL), manifest.appID == appID else { continue }
            let gameRoot = steamApps.appendingPathComponent("common", isDirectory: true)
                .appendingPathComponent(manifest.installDirectory, isDirectory: true)
            guard let bundle = resolveGameBundle(gameRoot) else { continue }
            return GameInstallation(
                root: bundle.root,
                appBundle: bundle.appBundle,
                dataDirectory: bundle.dataDirectory,
                steamAppID: manifest.appID,
                steamBuildID: manifest.buildID,
                steamManifest: manifest.url
            )
        }
        return nil
    }

    func resolveSteamInstallation(_ selectedURL: URL, appID: String) -> GameInstallation? {
        guard let bundle = resolveGameBundle(selectedURL) else { return nil }
        let common = bundle.root.deletingLastPathComponent()
        guard common.lastPathComponent == "common" else { return nil }
        let steamApps = common.deletingLastPathComponent()
        let manifestURL = steamApps.appendingPathComponent("appmanifest_\(appID).acf")
        guard let manifest = loadSteamManifest(manifestURL), manifest.appID == appID else { return nil }
        let manifestRoot = steamApps.appendingPathComponent("common", isDirectory: true)
            .appendingPathComponent(manifest.installDirectory, isDirectory: true)
            .standardizedFileURL
        guard manifestRoot == bundle.root.standardizedFileURL else { return nil }
        return GameInstallation(
            root: bundle.root,
            appBundle: bundle.appBundle,
            dataDirectory: bundle.dataDirectory,
            steamAppID: manifest.appID,
            steamBuildID: manifest.buildID,
            steamManifest: manifest.url
        )
    }

    private func resolveGameBundle(_ selectedURL: URL) -> (
        root: URL,
        appBundle: URL,
        dataDirectory: URL
    )? {
        let standardized = selectedURL.standardizedFileURL
        var appCandidates = [standardized]
        appCandidates.append(standardized.appendingPathComponent(Self.appName, isDirectory: true))

        if standardized.lastPathComponent == "Data" {
            appCandidates.append(
                standardized.deletingLastPathComponent()
                    .deletingLastPathComponent()
                    .deletingLastPathComponent()
            )
        }
        if standardized.lastPathComponent == "Resources" {
            appCandidates.append(
                standardized.deletingLastPathComponent().deletingLastPathComponent()
            )
        }

        for app in appCandidates {
            let executable = app.appendingPathComponent("Contents/MacOS/\(Self.executableName)")
            let data = app.appendingPathComponent(Self.dataRelativePath, isDirectory: true)
            let appInfo = data.appendingPathComponent("app.info")
            guard fileManager.fileExists(atPath: executable.path),
                  fileManager.fileExists(atPath: appInfo.path) else { continue }
            return (
                root: app.deletingLastPathComponent(),
                appBundle: app,
                dataDirectory: data
            )
        }
        return nil
    }

    private func steamLibraryRoots(steamRoot: URL) -> [URL] {
        var result = [steamRoot.standardizedFileURL]
        let libraries = steamRoot.appendingPathComponent("steamapps/libraryfolders.vdf")
        if let text = try? String(contentsOf: libraries, encoding: .utf8),
           let expression = try? NSRegularExpression(pattern: #"\"path\"\s+\"([^\"]+)\""#) {
            let nsText = text as NSString
            for match in expression.matches(in: text, range: NSRange(location: 0, length: nsText.length)) {
                guard match.numberOfRanges == 2 else { continue }
                let path = nsText.substring(with: match.range(at: 1))
                    .replacingOccurrences(of: "\\\\", with: "\\")
                result.append(URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL)
            }
        }
        var seen = Set<String>()
        return result.filter { seen.insert($0.path).inserted }
    }

    private func loadSteamManifest(_ url: URL) -> SteamManifest? {
        guard let text = try? String(contentsOf: url, encoding: .utf8),
              let appID = vdfValue("appid", in: text),
              let installDirectory = vdfValue("installdir", in: text),
              let buildID = vdfValue("buildid", in: text),
              !appID.isEmpty, !installDirectory.isEmpty, !buildID.isEmpty else { return nil }
        return SteamManifest(
            appID: appID,
            installDirectory: installDirectory,
            buildID: buildID,
            url: url.standardizedFileURL
        )
    }

    private func vdfValue(_ key: String, in text: String) -> String? {
        let escaped = NSRegularExpression.escapedPattern(for: key)
        guard let expression = try? NSRegularExpression(
            pattern: #"\""# + escaped + #"\"\s+\"([^\"]*)\""#,
            options: [.caseInsensitive]
        ) else { return nil }
        let nsText = text as NSString
        guard let match = expression.firstMatch(
            in: text,
            range: NSRange(location: 0, length: nsText.length)
        ), match.numberOfRanges == 2 else { return nil }
        return nsText.substring(with: match.range(at: 1))
    }

    func install(
        payload: URL,
        config: PackageConfig,
        selectedRuntimeCode: String,
        into installation: GameInstallation
    ) throws {
        try config.validate()
        guard config.payloadReady else { throw InstallerError.payloadNotReady }
        guard let selectedLanguage = config.languages.first(where: {
            $0.runtimeCode == selectedRuntimeCode && $0.ready
        }) else {
            throw InstallerError.invalidLanguageSelection(selectedRuntimeCode)
        }
        let selectedFiles = config.payloadFiles(for: selectedLanguage)
        guard installation.steamAppID == config.steamAppID else {
            throw InstallerError.wrongSteamApp(installation.steamAppID)
        }
        guard installation.steamBuildID == config.steamBuildID else {
            throw InstallerError.unsupportedSteamBuild(
                expected: config.steamBuildID,
                actual: installation.steamBuildID
            )
        }
        guard resolveSteamInstallation(installation.appBundle, appID: config.steamAppID) != nil else {
            throw InstallerError.invalidGameFolder
        }

        let stateRoot = installation.root.appendingPathComponent(".vn-revival", isDirectory: true)
            .appendingPathComponent(config.packageID, isDirectory: true)
        try fileManager.createDirectory(at: stateRoot, withIntermediateDirectories: true)
        try recoverInterruptedInstall(stateRoot: stateRoot, dataRoot: installation.dataDirectory)
        try migrateLegacyDevelopmentInstallIfPresent(
            installation: installation,
            stateRoot: stateRoot,
            config: config,
            selectedFiles: selectedFiles
        )

        let receiptURL = stateRoot.appendingPathComponent("receipt.json")
        let previousReceipt = try loadReceiptIfPresent(receiptURL, packageID: config.packageID)
        try validatePayload(payload, files: selectedFiles)

        let backupRoot = stateRoot.appendingPathComponent("original-backup", isDirectory: true)
        try fileManager.createDirectory(at: backupRoot, withIntermediateDirectories: true)
        var receiptFiles: [ReceiptFile] = []

        for item in selectedFiles {
            let destination = try safeURL(root: installation.dataDirectory, relativePath: item.path)
            let backup = try safeURL(root: backupRoot, relativePath: item.path)
            let currentExists = fileManager.fileExists(atPath: destination.path)
            let currentHash = currentExists ? try Self.sha256(of: destination) : nil
            let prior = previousReceipt?.files.first { $0.path == item.path }

            if let prior {
                guard currentHash == prior.installedSHA256 || currentHash == item.payloadSHA256 else {
                    throw InstallerError.foreignModification(item.path)
                }
            } else if let originalHash = item.originalSHA256 {
                guard currentExists else { throw InstallerError.missingOriginalFile(item.path) }
                guard currentHash == originalHash else { throw InstallerError.unsupportedGameFile(item.path) }
            } else if currentExists {
                throw InstallerError.foreignModification(item.path)
            }

            if let originalHash = item.originalSHA256 {
                if fileManager.fileExists(atPath: backup.path) {
                    guard try Self.sha256(of: backup) == originalHash else {
                        throw InstallerError.damagedBackup(item.path)
                    }
                } else {
                    try fileManager.createDirectory(
                        at: backup.deletingLastPathComponent(),
                        withIntermediateDirectories: true
                    )
                    try fileManager.copyItem(at: destination, to: backup)
                    guard try Self.sha256(of: backup) == originalHash else {
                        throw InstallerError.damagedBackup(item.path)
                    }
                }
            }

            receiptFiles.append(ReceiptFile(
                path: item.path,
                originalExisted: item.originalSHA256 != nil,
                originalSHA256: item.originalSHA256,
                installedSHA256: item.payloadSHA256!
            ))
        }

        let activePaths = Set(selectedFiles.map(\.path))
        let retiredFiles = previousReceipt?.files.filter { !activePaths.contains($0.path) } ?? []
        for prior in retiredFiles {
            let destination = try safeURL(root: installation.dataDirectory, relativePath: prior.path)
            let exists = fileManager.fileExists(atPath: destination.path)
            if exists {
                guard try Self.sha256(of: destination) == prior.installedSHA256 else {
                    throw InstallerError.foreignModification(prior.path)
                }
            } else if prior.originalExisted {
                throw InstallerError.foreignModification(prior.path)
            }
            if prior.originalExisted {
                guard let originalHash = prior.originalSHA256 else {
                    throw InstallerError.malformedReceipt
                }
                let backup = try safeURL(root: backupRoot, relativePath: prior.path)
                guard fileManager.fileExists(atPath: backup.path),
                      try Self.sha256(of: backup) == originalHash else {
                    throw InstallerError.damagedBackup(prior.path)
                }
            }
        }

        let transaction = stateRoot.appendingPathComponent("transaction", isDirectory: true)
        if fileManager.fileExists(atPath: transaction.path) { try fileManager.removeItem(at: transaction) }
        let rollback = transaction.appendingPathComponent("rollback", isDirectory: true)
        let staged = transaction.appendingPathComponent("staged", isDirectory: true)
        try fileManager.createDirectory(at: rollback, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: staged, withIntermediateDirectories: true)

        let transactionFiles = receiptFiles + retiredFiles
        for item in transactionFiles {
            let destination = try safeURL(root: installation.dataDirectory, relativePath: item.path)
            if fileManager.fileExists(atPath: destination.path) {
                let rollbackFile = try safeURL(root: rollback, relativePath: item.path)
                try fileManager.createDirectory(at: rollbackFile.deletingLastPathComponent(), withIntermediateDirectories: true)
                try fileManager.copyItem(at: destination, to: rollbackFile)
            }
        }
        let previousReceiptExisted = fileManager.fileExists(atPath: receiptURL.path)
        if previousReceiptExisted {
            try fileManager.copyItem(
                at: receiptURL,
                to: transaction.appendingPathComponent("previous-receipt.json")
            )
        }
        for item in selectedFiles {
            let stagedFile = try safeURL(root: staged, relativePath: item.path)
            try fileManager.createDirectory(at: stagedFile.deletingLastPathComponent(), withIntermediateDirectories: true)
            try stagePayloadFile(
                item,
                payload: payload,
                originalRoot: backupRoot,
                output: stagedFile,
                transaction: transaction
            )
            guard try Self.sha256(of: stagedFile) == item.payloadSHA256 else {
                throw InstallerError.payloadChecksumMismatch(item.path)
            }
        }

        let transactionURL = transaction.appendingPathComponent("state.json")
        var transactionState = TransactionState(
            schemaVersion: 1,
            packageID: config.packageID,
            committed: false,
            previousReceiptExisted: previousReceiptExisted,
            files: transactionFiles
        )
        try writeJSON(transactionState, to: transactionURL)

        do {
            for item in selectedFiles {
                let destination = try safeURL(root: installation.dataDirectory, relativePath: item.path)
                let stagedFile = try safeURL(root: staged, relativePath: item.path)
                try fileManager.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
                try replaceFile(at: destination, with: stagedFile)
            }
            for prior in retiredFiles {
                let destination = try safeURL(root: installation.dataDirectory, relativePath: prior.path)
                if prior.originalExisted {
                    let backup = try safeURL(root: backupRoot, relativePath: prior.path)
                    let restored = transaction.appendingPathComponent("restored", isDirectory: true)
                        .appendingPathComponent(prior.path)
                    try fileManager.createDirectory(at: restored.deletingLastPathComponent(), withIntermediateDirectories: true)
                    try fileManager.copyItem(at: backup, to: restored)
                    try replaceFile(at: destination, with: restored)
                } else if fileManager.fileExists(atPath: destination.path) {
                    try fileManager.removeItem(at: destination)
                }
            }
            let receipt = InstallationReceipt(
                schemaVersion: 1,
                packageID: config.packageID,
                steamBuildID: config.steamBuildID,
                installedAt: Date(),
                activeLanguage: ActiveLanguageSelection(
                    siteLocale: selectedLanguage.siteLocale,
                    runtimeCode: selectedLanguage.runtimeCode
                ),
                files: receiptFiles
            )
            try writeJSON(receipt, to: receiptURL)
            transactionState.committed = true
            try writeJSON(transactionState, to: transactionURL)
            try fileManager.removeItem(at: transaction)
        } catch {
            try? recoverInterruptedInstall(stateRoot: stateRoot, dataRoot: installation.dataDirectory)
            throw error
        }
    }

    func recoverInterruptedInstall(stateRoot: URL, dataRoot: URL) throws {
        let transaction = stateRoot.appendingPathComponent("transaction", isDirectory: true)
        let stateURL = transaction.appendingPathComponent("state.json")
        guard fileManager.fileExists(atPath: transaction.path) else { return }
        guard fileManager.fileExists(atPath: stateURL.path) else {
            try fileManager.removeItem(at: transaction)
            return
        }
        let state = try JSONDecoder().decode(TransactionState.self, from: Data(contentsOf: stateURL))
        guard state.schemaVersion == 1 else { throw InstallerError.malformedReceipt }
        if !state.committed {
            let rollback = transaction.appendingPathComponent("rollback", isDirectory: true)
            for item in state.files {
                let destination = try safeURL(root: dataRoot, relativePath: item.path)
                let rollbackFile = try safeURL(root: rollback, relativePath: item.path)
                if fileManager.fileExists(atPath: rollbackFile.path) {
                    try fileManager.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
                    try replaceFile(at: destination, with: rollbackFile)
                } else if !item.originalExisted && fileManager.fileExists(atPath: destination.path) {
                    try fileManager.removeItem(at: destination)
                }
            }
            if let previousReceiptExisted = state.previousReceiptExisted {
                let receiptURL = stateRoot.appendingPathComponent("receipt.json")
                let previousReceiptURL = transaction.appendingPathComponent("previous-receipt.json")
                if previousReceiptExisted {
                    guard fileManager.fileExists(atPath: previousReceiptURL.path) else {
                        throw InstallerError.malformedReceipt
                    }
                    try replaceFile(at: receiptURL, with: previousReceiptURL)
                } else if fileManager.fileExists(atPath: receiptURL.path) {
                    try fileManager.removeItem(at: receiptURL)
                }
            }
        }
        try fileManager.removeItem(at: transaction)
    }

    static func sha256(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private func migrateLegacyDevelopmentInstallIfPresent(
        installation: GameInstallation,
        stateRoot: URL,
        config: PackageConfig,
        selectedFiles: [PayloadFile]
    ) throws {
        let receiptURL = stateRoot.appendingPathComponent("receipt.json")
        guard !fileManager.fileExists(atPath: receiptURL.path) else { return }

        let legacyRoot = installation.root.appendingPathComponent(
            ".vn-revival/dev-russian-runtime",
            isDirectory: true
        )
        let legacyReceiptURL = legacyRoot.appendingPathComponent("receipt.json")
        guard fileManager.fileExists(atPath: legacyReceiptURL.path) else { return }

        let legacy = try JSONDecoder().decode(
            LegacyDevelopmentReceipt.self,
            from: Data(contentsOf: legacyReceiptURL)
        )
        let expected = selectedFiles.filter { $0.originalSHA256 != nil }
        guard legacy.kind == "russian-development-runtime-patch",
              legacy.steamAppId == config.steamAppID,
              legacy.steamBuildId == config.steamBuildID,
              legacy.targetLocale == "ru",
              legacy.files.count == expected.count,
              Set(legacy.files.map(\.path)) == Set(expected.map(\.path)) else {
            throw InstallerError.malformedReceipt
        }

        let backupRoot = stateRoot.appendingPathComponent("original-backup", isDirectory: true)
        let legacyBackupRoot = legacyRoot.appendingPathComponent("original-backup", isDirectory: true)
        var migratedFiles: [ReceiptFile] = []
        for item in expected {
            guard let originalSHA256 = item.originalSHA256,
                  let legacyFile = legacy.files.first(where: { $0.path == item.path }),
                  legacyFile.originalSha256 == originalSHA256,
                  PayloadFile.isSHA256(legacyFile.patchedSha256) else {
                throw InstallerError.malformedReceipt
            }
            let destination = try safeURL(root: installation.dataDirectory, relativePath: item.path)
            let legacyBackup = try safeURL(root: legacyBackupRoot, relativePath: item.path)
            guard fileManager.fileExists(atPath: destination.path),
                  fileManager.fileExists(atPath: legacyBackup.path),
                  try Self.sha256(of: destination) == legacyFile.patchedSha256,
                  try Self.sha256(of: legacyBackup) == originalSHA256 else {
                throw InstallerError.foreignModification(item.path)
            }
            let backup = try safeURL(root: backupRoot, relativePath: item.path)
            try fileManager.createDirectory(
                at: backup.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            if fileManager.fileExists(atPath: backup.path) {
                guard try Self.sha256(of: backup) == originalSHA256 else {
                    throw InstallerError.damagedBackup(item.path)
                }
            } else {
                try fileManager.copyItem(at: legacyBackup, to: backup)
            }
            migratedFiles.append(ReceiptFile(
                path: item.path,
                originalExisted: true,
                originalSHA256: originalSHA256,
                installedSHA256: legacyFile.patchedSha256
            ))
        }

        let migratedReceipt = InstallationReceipt(
            schemaVersion: 1,
            packageID: config.packageID,
            steamBuildID: config.steamBuildID,
            installedAt: Date(),
            activeLanguage: ActiveLanguageSelection(siteLocale: "ru", runtimeCode: "ru"),
            files: migratedFiles
        )
        try writeJSON(migratedReceipt, to: receiptURL)
    }

    private func validatePayload(_ payload: URL, files: [PayloadFile]) throws {
        for item in files {
            if let artifacts = item.artifacts {
                for artifact in artifacts {
                    try validateArtifact(
                        at: safeURL(root: payload, relativePath: artifact.path),
                        expectedSHA256: artifact.sha256,
                        owner: item.path
                    )
                }
            } else {
                let artifactPath = item.payloadPath ?? item.path
                try validateArtifact(
                    at: safeURL(root: payload, relativePath: artifactPath),
                    expectedSHA256: item.artifactSHA256 ?? item.payloadSHA256!,
                    owner: item.path
                )
            }
        }
    }

    private func validateArtifact(at url: URL, expectedSHA256: String, owner: String) throws {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory), !isDirectory.boolValue else {
            throw InstallerError.missingPayloadFile(owner)
        }
        let values = try url.resourceValues(forKeys: [.isSymbolicLinkKey])
        guard values.isSymbolicLink != true else { throw InstallerError.unsafePath(owner) }
        guard try Self.sha256(of: url) == expectedSHA256 else {
            throw InstallerError.payloadChecksumMismatch(owner)
        }
    }

    private func stagePayloadFile(
        _ item: PayloadFile,
        payload: URL,
        originalRoot: URL,
        output: URL,
        transaction: URL
    ) throws {
        guard let artifacts = item.artifacts else {
            let source = try safeURL(root: payload, relativePath: item.payloadPath ?? item.path)
            try fileManager.copyItem(at: source, to: output)
            return
        }
        let tool = payload.appendingPathComponent("Tools/xdelta3")
        guard fileManager.isExecutableFile(atPath: tool.path) else {
            throw InstallerError.deltaToolMissing
        }
        var source = try safeURL(root: originalRoot, relativePath: item.path)
        var intermediates: [URL] = []
        defer { intermediates.forEach { try? fileManager.removeItem(at: $0) } }
        for (index, artifact) in artifacts.enumerated() {
            let patch = try safeURL(root: payload, relativePath: artifact.path)
            let target: URL
            if index == artifacts.count - 1 {
                target = output
            } else {
                target = transaction.appendingPathComponent("delta-\(UUID().uuidString)")
                intermediates.append(target)
            }
            let process = Process()
            process.executableURL = tool
            process.arguments = ["-d", "-f", "-s", source.path, patch.path, target.path]
            let diagnostics = Pipe()
            process.standardOutput = diagnostics
            process.standardError = diagnostics
            try process.run()
            process.waitUntilExit()
            guard process.terminationReason == .exit, process.terminationStatus == 0 else {
                throw InstallerError.deltaApplicationFailed(item.path)
            }
            source = target
        }
    }

    private func safeURL(root: URL, relativePath: String) throws -> URL {
        guard PayloadFile.isSafeRelativePath(relativePath) else {
            throw InstallerError.unsafePath(relativePath)
        }
        let standardizedRoot = root.standardizedFileURL
        let result = standardizedRoot.appendingPathComponent(relativePath).standardizedFileURL
        guard result.path.hasPrefix(standardizedRoot.path + "/") else {
            throw InstallerError.unsafePath(relativePath)
        }
        return result
    }

    private func replaceFile(at destination: URL, with source: URL) throws {
        if fileManager.fileExists(atPath: destination.path) {
            _ = try fileManager.replaceItemAt(destination, withItemAt: source)
        } else {
            try fileManager.moveItem(at: source, to: destination)
        }
    }

    private func loadReceiptIfPresent(_ url: URL, packageID: String) throws -> InstallationReceipt? {
        guard fileManager.fileExists(atPath: url.path) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let receipt = try decoder.decode(InstallationReceipt.self, from: Data(contentsOf: url))
        guard receipt.schemaVersion == 1, receipt.packageID == packageID else {
            throw InstallerError.malformedReceipt
        }
        return receipt
    }

    private func writeJSON<T: Encodable>(_ value: T, to url: URL) throws {
        let data = try JSONEncoder.pretty.encode(value)
        try fileManager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url, options: .atomic)
    }
}

private extension JSONEncoder {
    static var pretty: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
}
