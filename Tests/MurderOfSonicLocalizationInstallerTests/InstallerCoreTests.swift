import CryptoKit
import Foundation
import Testing
@testable import MurderOfSonicLocalizationInstaller

@Suite
struct InstallerCoreTests {
    private let fileManager = FileManager.default

    @Test func packageConfigLoadsReadyThirtyLocalePayload() throws {
        let url = projectRoot().appendingPathComponent(
            "Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"
        )
        let config = try PackageConfig.load(from: url)
        #expect(config.schemaVersion == 2)
        #expect(config.sourceLocale == "en")
        #expect(config.steamAppID == "2324650")
        #expect(config.steamBuildID == "20535215")
        #expect(config.gameVersion == "1.01")
        #expect(config.languages.count == 30)
        #expect(Set(config.languages.map(\.siteLocale)) == PackageConfig.requiredSiteLocales)
        #expect(Set(config.languages.map(\.runtimeCode)) == PackageConfig.requiredSiteLocales)
        #expect(config.languages.allSatisfy { $0.ready })
        #expect(config.languages.allSatisfy { !(config.payloadFiles(for: $0)).isEmpty })
        #expect(config.payloadReady == true)
        #expect(config.files.isEmpty)
    }

    @Test func rejectsTraversalAndMalformedReadyPayload() throws {
        var config = makeConfig(files: [PayloadFile(
            path: "../outside",
            originalSHA256: nil,
            payloadSHA256: String(repeating: "a", count: 64)
        )])
        #expect(throws: PackageConfigError.self) { try config.validate() }

        config = makeConfig(files: [])
        #expect(throws: PackageConfigError.self) { try config.validate() }
    }

    @Test func rejectsMissingOrIncompleteLanguageSet() throws {
        let file = PayloadFile(
            path: "Managed/Assembly-CSharp.dll",
            originalSHA256: sha256("original"),
            payloadSHA256: sha256("translated")
        )
        var config = makeConfig(files: [file])
        config = PackageConfig(
            schemaVersion: config.schemaVersion,
            packageID: config.packageID,
            sourceLocale: config.sourceLocale,
            languages: Array(config.languages.dropLast()),
            steamAppID: config.steamAppID,
            steamBuildID: config.steamBuildID,
            gameVersion: config.gameVersion,
            unityVersion: config.unityVersion,
            payloadReady: config.payloadReady,
            files: config.files,
            copy: config.copy
        )
        #expect(throws: PackageConfigError.self) { try config.validate() }

        let incompleteLanguages = completeLanguages().enumerated().map { index, language in
            LanguagePackage(
                siteLocale: language.siteLocale,
                runtimeCode: language.runtimeCode,
                nativeLanguageName: language.nativeLanguageName,
                ready: index != 0
            )
        }
        config = PackageConfig(
            schemaVersion: 2,
            packageID: "fun.vnrevival.test",
            sourceLocale: "en",
            languages: incompleteLanguages,
            steamAppID: "2324650",
            steamBuildID: "20535215",
            gameVersion: "1.01",
            unityVersion: "2021.3.9f1",
            payloadReady: true,
            files: [file],
            copy: .testCopy
        )
        #expect(throws: PackageConfigError.self) { try config.validate() }
    }

    @Test func detectsSteamInstallationInConfiguredLibrary() throws {
        try withTemporaryDirectory { root in
            let steamRoot = root.appendingPathComponent("Steam", isDirectory: true)
            let libraryRoot = root.appendingPathComponent("ExternalLibrary", isDirectory: true)
            let setup = try makeSteamInstallation(
                libraryRoot: libraryRoot,
                original: "original"
            )
            let escapedLibrary = libraryRoot.path.replacingOccurrences(of: "\\", with: "\\\\")
            let libraryFolders = """
            "libraryfolders"
            {
                "0"
                {
                    "path" "\(escapedLibrary)"
                }
            }
            """
            try write(
                Data(libraryFolders.utf8),
                to: steamRoot.appendingPathComponent("steamapps/libraryfolders.vdf")
            )

            let core = InstallerCore()
            let detected = try #require(core.detectSteamInstallation(
                appID: "2324650",
                steamRoot: steamRoot
            ))
            let fromRoot = try #require(core.resolveSteamInstallation(
                setup.installation.root,
                appID: "2324650"
            ))
            let fromApp = try #require(core.resolveSteamInstallation(
                setup.installation.appBundle,
                appID: "2324650"
            ))
            let fromData = try #require(core.resolveSteamInstallation(
                setup.installation.dataDirectory,
                appID: "2324650"
            ))
            #expect(detected == setup.installation)
            #expect(fromApp == fromRoot)
            #expect(fromData == fromRoot)
            #expect(detected.steamAppID == "2324650")
            #expect(detected.steamBuildID == "20535215")
            #expect(detected.steamManifest.lastPathComponent == "appmanifest_2324650.acf")
        }
    }

    @Test func ignoresManifestForAnotherSteamApp() throws {
        try withTemporaryDirectory { root in
            let steamRoot = root.appendingPathComponent("Steam", isDirectory: true)
            _ = try makeSteamInstallation(
                libraryRoot: steamRoot,
                original: "original",
                manifestAppID: "999999"
            )
            #expect(InstallerCore().detectSteamInstallation(
                appID: "2324650",
                steamRoot: steamRoot
            ) == nil)
        }
    }

    @Test func installsBacksUpAndUpdatesOwnedPayload() throws {
        try withTemporaryDirectory { root in
            let setup = try makeFakeInstallation(root: root, original: "original")
            let firstPayload = root.appendingPathComponent("payload-one", isDirectory: true)
            let relative = "Managed/Assembly-CSharp.dll"
            try write(Data("russian-v1".utf8), to: firstPayload.appendingPathComponent(relative))
            let originalHash = try InstallerCore.sha256(of: setup.file)
            let firstHash = try InstallerCore.sha256(of: firstPayload.appendingPathComponent(relative))
            let firstConfig = makeConfig(files: [PayloadFile(
                path: relative,
                originalSHA256: originalHash,
                payloadSHA256: firstHash
            )])

            let core = InstallerCore()
            try core.install(
                payload: firstPayload,
                config: firstConfig,
                selectedRuntimeCode: "ru",
                into: setup.installation
            )
            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "russian-v1")

            let receiptURL = setup.installation.root
                .appendingPathComponent(".vn-revival/\(firstConfig.packageID)/receipt.json")
            let firstReceipt = try JSONDecoder.iso8601.decode(
                InstallationReceipt.self,
                from: Data(contentsOf: receiptURL)
            )
            #expect(firstReceipt.activeLanguage == ActiveLanguageSelection(
                siteLocale: "ru",
                runtimeCode: "ru"
            ))

            let backup = setup.installation.root
                .appendingPathComponent(".vn-revival/\(firstConfig.packageID)/original-backup")
                .appendingPathComponent(relative)
            #expect(try String(contentsOf: backup, encoding: .utf8) == "original")

            let secondPayload = root.appendingPathComponent("payload-two", isDirectory: true)
            try write(Data("russian-v2".utf8), to: secondPayload.appendingPathComponent(relative))
            let secondHash = try InstallerCore.sha256(of: secondPayload.appendingPathComponent(relative))
            let secondConfig = makeConfig(files: [PayloadFile(
                path: relative,
                originalSHA256: originalHash,
                payloadSHA256: secondHash
            )])
            try core.install(
                payload: secondPayload,
                config: secondConfig,
                selectedRuntimeCode: "de",
                into: setup.installation
            )
            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "russian-v2")
            #expect(try String(contentsOf: backup, encoding: .utf8) == "original")
            let secondReceipt = try JSONDecoder.iso8601.decode(
                InstallationReceipt.self,
                from: Data(contentsOf: receiptURL)
            )
            #expect(secondReceipt.activeLanguage == ActiveLanguageSelection(
                siteLocale: "de",
                runtimeCode: "de"
            ))
        }
    }

    @Test func rejectsUnknownLanguageBeforeChangingGame() throws {
        try withTemporaryDirectory { root in
            let setup = try makeFakeInstallation(root: root, original: "original")
            let payload = root.appendingPathComponent("payload", isDirectory: true)
            let relative = "Managed/Assembly-CSharp.dll"
            try write(Data("translated".utf8), to: payload.appendingPathComponent(relative))
            let config = makeConfig(files: [PayloadFile(
                path: relative,
                originalSHA256: try InstallerCore.sha256(of: setup.file),
                payloadSHA256: try InstallerCore.sha256(of: payload.appendingPathComponent(relative))
            )])

            #expect(throws: InstallerError.self) {
                try InstallerCore().install(
                    payload: payload,
                    config: config,
                    selectedRuntimeCode: "not-a-locale",
                    into: setup.installation
                )
            }
            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "original")
        }
    }

    @Test func reconstructsAndInstallsVerifiedDeltaPayload() throws {
        try withTemporaryDirectory { root in
            let setup = try makeFakeInstallation(root: root, original: "original")
            let payload = root.appendingPathComponent("payload", isDirectory: true)
            let tool = payload.appendingPathComponent("Tools/xdelta3")
            let bundledTool = projectRoot().appendingPathComponent(
                "Sources/MurderOfSonicLocalizationInstaller/Resources/LocalizationPayload/Tools/xdelta3"
            )
            try fileManager.createDirectory(at: tool.deletingLastPathComponent(), withIntermediateDirectories: true)
            try fileManager.copyItem(at: bundledTool, to: tool)
            try fileManager.setAttributes([.posixPermissions: 0o755], ofItemAtPath: tool.path)

            let translated = root.appendingPathComponent("translated")
            try write(Data("localized".utf8), to: translated)
            let delta = payload.appendingPathComponent("ru/managed.xdelta")
            try fileManager.createDirectory(at: delta.deletingLastPathComponent(), withIntermediateDirectories: true)
            try runProcess(tool, [
                "-a", "-S", "djw", "-1", "-e", "-f",
                "-s", setup.file.path, translated.path, delta.path,
            ])
            let relative = "Managed/Assembly-CSharp.dll"
            let config = makeConfig(files: [PayloadFile(
                path: relative,
                originalSHA256: try InstallerCore.sha256(of: setup.file),
                payloadSHA256: try InstallerCore.sha256(of: translated),
                artifacts: [PayloadArtifact(
                    path: "ru/managed.xdelta",
                    sha256: try InstallerCore.sha256(of: delta)
                )]
            )])

            try InstallerCore().install(
                payload: payload,
                config: config,
                selectedRuntimeCode: "ru",
                into: setup.installation
            )
            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "localized")
        }
    }

    @Test func interruptedInstallRestoresFilesAndPreviousLanguageReceipt() throws {
        try withTemporaryDirectory { root in
            let dataRoot = root.appendingPathComponent("Data", isDirectory: true)
            let stateRoot = root.appendingPathComponent("state", isDirectory: true)
            let transaction = stateRoot.appendingPathComponent("transaction", isDirectory: true)
            let relative = "Managed/Assembly-CSharp.dll"
            let installedFile = dataRoot.appendingPathComponent(relative)
            let rollbackFile = transaction.appendingPathComponent("rollback/\(relative)")
            let receiptURL = stateRoot.appendingPathComponent("receipt.json")
            let previousReceiptURL = transaction.appendingPathComponent("previous-receipt.json")
            try write(Data("new-payload".utf8), to: installedFile)
            try write(Data("old-payload".utf8), to: rollbackFile)
            try write(Data("new-language-receipt".utf8), to: receiptURL)
            try write(Data("old-language-receipt".utf8), to: previousReceiptURL)

            let state = TransactionState(
                schemaVersion: 1,
                packageID: "fun.vnrevival.test",
                committed: false,
                previousReceiptExisted: true,
                files: [ReceiptFile(
                    path: relative,
                    originalExisted: true,
                    originalSHA256: sha256("original"),
                    installedSHA256: sha256("new-payload")
                )]
            )
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            try write(try encoder.encode(state), to: transaction.appendingPathComponent("state.json"))

            try InstallerCore().recoverInterruptedInstall(stateRoot: stateRoot, dataRoot: dataRoot)

            #expect(try String(contentsOf: installedFile, encoding: .utf8) == "old-payload")
            #expect(try String(contentsOf: receiptURL, encoding: .utf8) == "old-language-receipt")
            #expect(!fileManager.fileExists(atPath: transaction.path))
        }
    }

    @Test func refusesForeignModification() throws {
        try withTemporaryDirectory { root in
            let setup = try makeFakeInstallation(root: root, original: "modified-by-other-mod")
            let payload = root.appendingPathComponent("payload", isDirectory: true)
            let relative = "Managed/Assembly-CSharp.dll"
            try write(Data("russian".utf8), to: payload.appendingPathComponent(relative))
            let config = makeConfig(files: [PayloadFile(
                path: relative,
                originalSHA256: sha256("expected-original"),
                payloadSHA256: try InstallerCore.sha256(of: payload.appendingPathComponent(relative))
            )])
            let core = InstallerCore()
            #expect(throws: InstallerError.self) {
                try core.install(
                    payload: payload,
                    config: config,
                    selectedRuntimeCode: "ru",
                    into: setup.installation
                )
            }
            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "modified-by-other-mod")
        }
    }

    @Test func updateRestoresRetiredOriginalFile() throws {
        try withTemporaryDirectory { root in
            let setup = try makeFakeInstallation(root: root, original: "original")
            let replaced = "Managed/Assembly-CSharp.dll"
            let added = "StreamingAssets/aa/russian.bundle"
            let firstPayload = root.appendingPathComponent("payload-one", isDirectory: true)
            try write(Data("russian-code".utf8), to: firstPayload.appendingPathComponent(replaced))
            try write(Data("russian-bundle-v1".utf8), to: firstPayload.appendingPathComponent(added))
            let firstConfig = makeConfig(files: [
                PayloadFile(
                    path: replaced,
                    originalSHA256: try InstallerCore.sha256(of: setup.file),
                    payloadSHA256: try InstallerCore.sha256(of: firstPayload.appendingPathComponent(replaced))
                ),
                PayloadFile(
                    path: added,
                    originalSHA256: nil,
                    payloadSHA256: try InstallerCore.sha256(of: firstPayload.appendingPathComponent(added))
                ),
            ])
            let core = InstallerCore()
            try core.install(
                payload: firstPayload,
                config: firstConfig,
                selectedRuntimeCode: "ru",
                into: setup.installation
            )

            let secondPayload = root.appendingPathComponent("payload-two", isDirectory: true)
            try write(Data("russian-bundle-v2".utf8), to: secondPayload.appendingPathComponent(added))
            let secondConfig = makeConfig(files: [PayloadFile(
                path: added,
                originalSHA256: nil,
                payloadSHA256: try InstallerCore.sha256(of: secondPayload.appendingPathComponent(added))
            )])
            try core.install(
                payload: secondPayload,
                config: secondConfig,
                selectedRuntimeCode: "ru",
                into: setup.installation
            )

            #expect(try String(contentsOf: setup.file, encoding: .utf8) == "original")
            let addedFile = setup.installation.dataDirectory.appendingPathComponent(added)
            #expect(try String(contentsOf: addedFile, encoding: .utf8) == "russian-bundle-v2")
        }
    }

    private func makeConfig(files: [PayloadFile]) -> PackageConfig {
        PackageConfig(
            schemaVersion: 2,
            packageID: "fun.vnrevival.test",
            sourceLocale: "en",
            languages: completeLanguages(),
            steamAppID: "2324650",
            steamBuildID: "20535215",
            gameVersion: "1.01",
            unityVersion: "2021.3.9f1",
            payloadReady: true,
            files: files,
            copy: .testCopy
        )
    }

    private func completeLanguages() -> [LanguagePackage] {
        PackageConfig.requiredSiteLocales.sorted().map {
            LanguagePackage(siteLocale: $0, runtimeCode: $0, nativeLanguageName: $0, ready: true)
        }
    }

    private func makeFakeInstallation(root: URL, original: String) throws -> (installation: GameInstallation, file: URL) {
        let steamRoot = root.appendingPathComponent("Steam", isDirectory: true)
        return try makeSteamInstallation(
            libraryRoot: steamRoot,
            original: original
        )
    }

    private func makeSteamInstallation(
        libraryRoot: URL,
        original: String,
        manifestAppID: String = "2324650",
        buildID: String = "20535215"
    ) throws -> (installation: GameInstallation, file: URL) {
        let installDirectory = "Themurderofsonicthehedgehog"
        let steamApps = libraryRoot.appendingPathComponent("steamapps", isDirectory: true)
        let gameRoot = steamApps.appendingPathComponent("common/\(installDirectory)", isDirectory: true)
        let app = gameRoot.appendingPathComponent(InstallerCore.appName, isDirectory: true)
        let executable = app.appendingPathComponent("Contents/MacOS/\(InstallerCore.executableName)")
        let data = app.appendingPathComponent(InstallerCore.dataRelativePath, isDirectory: true)
        let appInfo = data.appendingPathComponent("app.info")
        let file = data.appendingPathComponent("Managed/Assembly-CSharp.dll")
        let manifest = steamApps.appendingPathComponent("appmanifest_2324650.acf")
        let manifestText = """
        "AppState"
        {
            "appid" "\(manifestAppID)"
            "installdir" "\(installDirectory)"
            "buildid" "\(buildID)"
        }
        """
        try write(Data("binary".utf8), to: executable)
        try write(Data("Sonic Social".utf8), to: appInfo)
        try write(Data(original.utf8), to: file)
        try write(Data(manifestText.utf8), to: manifest)
        let installation = GameInstallation(
            root: gameRoot.standardizedFileURL,
            appBundle: app.standardizedFileURL,
            dataDirectory: data.standardizedFileURL,
            steamAppID: manifestAppID,
            steamBuildID: buildID,
            steamManifest: manifest.standardizedFileURL
        )
        return (installation, file)
    }

    private func write(_ data: Data, to url: URL) throws {
        try fileManager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }

    private func runProcess(_ executable: URL, _ arguments: [String]) throws {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        try process.run()
        process.waitUntilExit()
        #expect(process.terminationReason == .exit)
        #expect(process.terminationStatus == 0)
    }

    private func withTemporaryDirectory(_ body: (URL) throws -> Void) throws {
        let root = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try fileManager.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: root) }
        try body(root)
    }

    private func projectRoot() -> URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }

    private func sha256(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}

private extension InstallerCopy {
    static let testCopy = InstallerCopy(
        windowTitle: "test", selectLanguageTitle: "test", preparingTitle: "test", installingTitle: "test",
        readyTitle: "test", failedTitle: "test", selectLanguageMessage: "test",
        languagePickerLabel: "test", preparingMessage: "test",
        findingGameMessage: "test", gameNotFoundMessage: "test", chooseGameTitle: "test",
        chooseGameMessage: "test", chooseGamePrompt: "test", installingMessage: "test",
        installedMessage: "test", launchingMessage: "test", steamFailedMessage: "test",
        installationErrorMessage: "test", payloadNotReadyMessage: "test", installButton: "test",
        changeLanguageButton: "test", launchButton: "test",
        chooseGameButton: "test", retryButton: "test", waitHint: "test"
    )
}

private extension JSONDecoder {
    static var iso8601: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
