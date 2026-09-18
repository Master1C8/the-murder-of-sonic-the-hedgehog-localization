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

struct LanguagePackage: Codable, Equatable, Sendable {
    let siteLocale: String
    let runtimeCode: String
    let nativeLanguageName: String
    let ready: Bool
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
        if payloadReady && files.isEmpty { throw PackageConfigError.emptyReadyPayload }
        try files.forEach { try $0.validate(ready: payloadReady) }
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

    var errorDescription: String? {
        switch self {
        case .unsupportedSchema(let value): "Неподдерживаемая версия конфигурации: \(value)."
        case .unsupportedSourceLocale(let value): "Неподдерживаемый язык оригинала: \(value)."
        case .missingValue: "В конфигурации пакета отсутствует обязательное значение."
        case .invalidPackageID: "Идентификатор пакета содержит недопустимые символы."
        case .duplicatePath: "В конфигурации пакета повторяется путь файла."
        case .invalidLanguageSet: "Мультипатч должен содержать все 30 локалей VN Revival."
        case .invalidLanguageMetadata: "Коды или названия языков мультипатча некорректны."
        case .incompleteLanguages: "Не все 30 языков мультипатча готовы к выпуску."
        case .emptyReadyPayload: "Готовый пакет не может быть пустым."
        case .unsafePath(let path): "Небезопасный путь в пакете: \(path)."
        case .invalidHash(let path): "Некорректная контрольная сумма файла: \(path)."
        }
    }
}
