import Foundation

struct InstallerCopy: Codable, Equatable, Sendable {
    let windowTitle: String
    let selectLanguageTitle: String
    let preparingTitle: String
    let installingTitle: String
    let readyTitle: String
    let failedTitle: String
    let selectLanguageMessage: String
    let languagePickerLabel: String
    let preparingMessage: String
    let findingGameMessage: String
    let gameNotFoundMessage: String
    let chooseGameTitle: String
    let chooseGameMessage: String
    let chooseGamePrompt: String
    let installingMessage: String
    let installedMessage: String
    let launchingMessage: String
    let steamFailedMessage: String
    let installationErrorMessage: String
    let payloadNotReadyMessage: String
    let installButton: String
    let changeLanguageButton: String
    let launchButton: String
    let chooseGameButton: String
    let retryButton: String
    let waitHint: String
}

struct PayloadFile: Codable, Equatable, Sendable {
    let path: String
    let originalSHA256: String?
    let payloadSHA256: String?
    let payloadPath: String?
    let artifactSHA256: String?
    let artifacts: [PayloadArtifact]?

    init(
        path: String,
        originalSHA256: String?,
        payloadSHA256: String?,
        payloadPath: String? = nil,
        artifactSHA256: String? = nil,
        artifacts: [PayloadArtifact]? = nil
    ) {
        self.path = path
        self.originalSHA256 = originalSHA256
        self.payloadSHA256 = payloadSHA256
        self.payloadPath = payloadPath
        self.artifactSHA256 = artifactSHA256
        self.artifacts = artifacts
    }

    func validate(ready: Bool) throws {
        guard Self.isSafeRelativePath(path) else {
            throw PackageConfigError.unsafePath(path)
        }
        if let originalSHA256 {
            guard Self.isSHA256(originalSHA256) else {
                throw PackageConfigError.invalidHash(path)
            }
        }
        if ready {
            guard let payloadSHA256, Self.isSHA256(payloadSHA256) else {
                throw PackageConfigError.invalidHash(path)
            }
        } else if let payloadSHA256, !Self.isSHA256(payloadSHA256) {
            throw PackageConfigError.invalidHash(path)
        }
        if let artifacts {
            guard !artifacts.isEmpty else { throw PackageConfigError.emptyArtifactChain(path) }
            guard originalSHA256 != nil else { throw PackageConfigError.deltaWithoutOriginal(path) }
            guard payloadPath == nil, artifactSHA256 == nil else {
                throw PackageConfigError.ambiguousArtifact(path)
            }
            try artifacts.forEach { try $0.validate(owner: path) }
        } else {
            let artifactPath = payloadPath ?? path
            guard Self.isSafeRelativePath(artifactPath) else {
                throw PackageConfigError.unsafePath(artifactPath)
            }
            if let artifactSHA256, !Self.isSHA256(artifactSHA256) {
                throw PackageConfigError.invalidArtifactHash(path)
            }
        }
    }

    static func isSafeRelativePath(_ value: String) -> Bool {
        guard !value.isEmpty, !value.hasPrefix("/"), !value.contains("\\") else { return false }
        let components = value.split(separator: "/", omittingEmptySubsequences: false)
        return components.allSatisfy { !$0.isEmpty && $0 != "." && $0 != ".." }
    }

    static func isSHA256(_ value: String) -> Bool {
        value.count == 64 && value.allSatisfy { $0.isHexDigit }
    }
}

struct PayloadArtifact: Codable, Equatable, Sendable {
    let path: String
    let sha256: String

    func validate(owner: String) throws {
        guard PayloadFile.isSafeRelativePath(path) else {
            throw PackageConfigError.unsafePath(path)
        }
        guard PayloadFile.isSHA256(sha256) else {
            throw PackageConfigError.invalidArtifactHash(owner)
        }
    }
}

struct LanguagePackage: Codable, Equatable, Sendable {
    let siteLocale: String
    let runtimeCode: String
    let nativeLanguageName: String
    let ready: Bool
    let files: [PayloadFile]?

    init(
        siteLocale: String,
        runtimeCode: String,
        nativeLanguageName: String,
        ready: Bool,
        files: [PayloadFile]? = nil
    ) {
        self.siteLocale = siteLocale
        self.runtimeCode = runtimeCode
        self.nativeLanguageName = nativeLanguageName
        self.ready = ready
        self.files = files
    }
}

struct ActiveLanguageSelection: Codable, Equatable, Sendable {
    let siteLocale: String
    let runtimeCode: String
}

struct PackageConfig: Codable, Equatable, Sendable {
    static let requiredSiteLocales: Set<String> = [
        "zh", "ru", "es", "es-419", "pt-BR", "ja", "de", "ko", "fr", "tr", "pl",
        "zh-TW", "it", "th", "vi", "id", "uk", "ar", "cs", "hu", "nl", "fa", "ro",
        "hi", "fil", "el", "bg", "sr", "sw", "he",
    ]

    let schemaVersion: Int
    let packageID: String
    let sourceLocale: String
    let languages: [LanguagePackage]
    let steamAppID: String
    let steamBuildID: String
    let gameVersion: String
    let unityVersion: String
    let payloadReady: Bool
    let files: [PayloadFile]
    let copy: InstallerCopy

    static func load(from url: URL) throws -> PackageConfig {
        let config = try JSONDecoder().decode(PackageConfig.self, from: Data(contentsOf: url))
        try config.validate()
        return config
    }

    func validate() throws {
        guard schemaVersion == 2 else { throw PackageConfigError.unsupportedSchema(schemaVersion) }
        guard sourceLocale == "en" else { throw PackageConfigError.unsupportedSourceLocale(sourceLocale) }
        let required = [packageID, steamAppID, steamBuildID, gameVersion, unityVersion]
        guard required.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else {
            throw PackageConfigError.missingValue
        }
        guard packageID.allSatisfy({ $0.isLetter || $0.isNumber || ".-_".contains($0) }) else {
            throw PackageConfigError.invalidPackageID
        }
        guard Set(files.map(\.path)).count == files.count else {
            throw PackageConfigError.duplicatePath
        }
        guard languages.count == Self.requiredSiteLocales.count,
              Set(languages.map(\.siteLocale)) == Self.requiredSiteLocales else {
            throw PackageConfigError.invalidLanguageSet
        }
        guard Set(languages.map(\.runtimeCode)).count == languages.count,
              languages.allSatisfy({
                  !$0.runtimeCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                      && !$0.nativeLanguageName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
              }) else {
            throw PackageConfigError.invalidLanguageMetadata
        }
        if payloadReady && !languages.allSatisfy(\.ready) {
            throw PackageConfigError.incompleteLanguages
        }
        if payloadReady && languages.contains(where: { payloadFiles(for: $0).isEmpty }) {
            throw PackageConfigError.emptyReadyPayload
        }
        try files.forEach { try $0.validate(ready: payloadReady) }
        for language in languages {
            let selectedFiles = payloadFiles(for: language)
            guard Set(selectedFiles.map(\.path)).count == selectedFiles.count else {
                throw PackageConfigError.duplicatePath
            }
            try selectedFiles.forEach { try $0.validate(ready: payloadReady) }
        }
    }

    func payloadFiles(for language: LanguagePackage) -> [PayloadFile] {
        language.files ?? files
    }
}

enum PackageConfigError: LocalizedError {
    case unsupportedSchema(Int)
    case unsupportedSourceLocale(String)
    case missingValue
    case invalidPackageID
    case duplicatePath
    case invalidLanguageSet
    case invalidLanguageMetadata
    case incompleteLanguages
    case emptyReadyPayload
    case unsafePath(String)
    case invalidHash(String)
    case invalidArtifactHash(String)
    case emptyArtifactChain(String)
    case deltaWithoutOriginal(String)
    case ambiguousArtifact(String)

    var errorDescription: String? {
        switch self {
        case .unsupportedSchema(let value): "Unsupported configuration version: \(value)."
        case .unsupportedSourceLocale(let value): "Unsupported source language: \(value)."
        case .missingValue: "A required value is missing from the package configuration."
        case .invalidPackageID: "The package identifier contains invalid characters."
        case .duplicatePath: "The package configuration contains a duplicate file path."
        case .invalidLanguageSet: "The package must contain all 30 VN Revival locales."
        case .invalidLanguageMetadata: "The package contains invalid language codes or names."
        case .incompleteLanguages: "Not all 30 package languages are ready for release."
        case .emptyReadyPayload: "A ready package cannot be empty."
        case .unsafePath(let path): "Unsafe path in the package: \(path)."
        case .invalidHash(let path): "Invalid file checksum: \(path)."
        case .invalidArtifactHash(let path): "Invalid delta checksum for file: \(path)."
        case .emptyArtifactChain(let path): "Empty delta chain for file: \(path)."
        case .deltaWithoutOriginal(let path): "A delta requires a verified original file: \(path)."
        case .ambiguousArtifact(let path): "The file defines both a full payload and a delta chain: \(path)."
        }
    }
}
