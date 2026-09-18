import AppKit
import Foundation

enum InstallerPhase: Equatable {
    case choosingLanguage
    case preparing
    case installing
    case ready
    case failed
}

@MainActor
final class AppState: ObservableObject {
    @Published private(set) var phase: InstallerPhase = .choosingLanguage
    @Published private(set) var message: String
    @Published private(set) var copy: InstallerCopy
    @Published var selectedRuntimeCode = ""

    private var installation: GameInstallation?
    private var config: PackageConfig?
    private var loadError: Error?
    private var hasStarted = false
    private let core = InstallerCore()

    init() {
        let fallback = InstallerCopy.fallback
        copy = fallback
        message = fallback.preparingMessage
        do {
            let loaded = try PackageConfig.load(from: Self.configURL())
            config = loaded
            copy = loaded.copy
            selectedRuntimeCode = Self.preferredRuntimeCode(in: loaded.languages)
            message = loaded.copy.selectLanguageMessage
        } catch {
            loadError = error
            phase = .failed
            message = error.localizedDescription
        }
    }

    var availableLanguages: [LanguagePackage] {
        config?.languages ?? []
    }

    var phaseTitle: String {
        switch phase {
        case .choosingLanguage: copy.selectLanguageTitle
        case .preparing: copy.preparingTitle
        case .installing: copy.installingTitle
        case .ready: copy.readyTitle
        case .failed: copy.failedTitle
        }
    }

    func start() async {
        guard !hasStarted else { return }
        guard !selectedRuntimeCode.isEmpty else { return }
        hasStarted = true
        phase = .preparing
        message = copy.findingGameMessage

        guard let config else {
            return fail(loadError?.localizedDescription ?? copy.installationErrorMessage)
        }
        if installation == nil {
            installation = core.detectSteamInstallation(appID: config.steamAppID)
        }
        guard let installation else { return fail(copy.gameNotFoundMessage) }
        guard installation.steamBuildID == config.steamBuildID else {
            return fail(InstallerError.unsupportedSteamBuild(
                expected: config.steamBuildID,
                actual: installation.steamBuildID
            ).localizedDescription)
        }
        guard config.payloadReady else { return fail(copy.payloadNotReadyMessage) }

        phase = .installing
        message = copy.installingMessage
        do {
            let payload = try Self.payloadURL()
            let selectedRuntimeCode = selectedRuntimeCode
            try await Task.detached(priority: .userInitiated) {
                try InstallerCore().install(
                    payload: payload,
                    config: config,
                    selectedRuntimeCode: selectedRuntimeCode,
                    into: installation
                )
            }.value
            phase = .ready
            let languageName = config.languages.first {
                $0.runtimeCode == selectedRuntimeCode
            }?.nativeLanguageName ?? selectedRuntimeCode
            message = "\(copy.installedMessage): \(languageName)"
        } catch {
            let details = error.localizedDescription.trimmingCharacters(in: .whitespacesAndNewlines)
            fail(details.isEmpty ? copy.installationErrorMessage : details)
        }
    }

    func retry() async {
        hasStarted = false
        await start()
    }

    func chooseAnotherLanguage() {
        guard config != nil else { return }
        hasStarted = false
        phase = .choosingLanguage
        message = copy.selectLanguageMessage
    }

    func chooseGameFolder() async {
        let panel = NSOpenPanel()
        panel.title = copy.chooseGameTitle
        panel.message = copy.chooseGameMessage
        panel.prompt = copy.chooseGamePrompt
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard let config else {
            return fail(loadError?.localizedDescription ?? copy.installationErrorMessage)
        }
        guard let found = core.resolveSteamInstallation(url, appID: config.steamAppID) else {
            return fail(copy.gameNotFoundMessage)
        }
        installation = found
        await retry()
    }

    func launchGame() {
        guard phase == .ready, let config else { return }
        guard let steamURL = URL(string: "steam://rungameid/\(config.steamAppID)"),
              NSWorkspace.shared.open(steamURL) else {
            return fail(copy.steamFailedMessage)
        }
        message = copy.launchingMessage
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            NSApplication.shared.terminate(nil)
        }
    }

    private static func configURL() throws -> URL {
        guard let url = Bundle.module.url(forResource: "PackageConfig", withExtension: "json") else {
            throw InstallerError.missingPayloadFile("PackageConfig.json")
        }
        return url
    }

    private static func payloadURL() throws -> URL {
        guard let url = Bundle.module.url(forResource: "LocalizationPayload", withExtension: nil) else {
            throw InstallerError.missingPayloadFile("LocalizationPayload")
        }
        return url
    }

    private func fail(_ text: String) {
        phase = .failed
        message = text
    }


    private static func preferredRuntimeCode(in languages: [LanguagePackage]) -> String {
        let normalizedPreferences = Locale.preferredLanguages.map {
            $0.replacingOccurrences(of: "_", with: "-")
        }
        for preference in normalizedPreferences {
            if let exact = languages.first(where: {
                $0.runtimeCode.caseInsensitiveCompare(preference) == .orderedSame
                    || $0.siteLocale.caseInsensitiveCompare(preference) == .orderedSame
            }) {
                return exact.runtimeCode
            }
        }
        for preference in normalizedPreferences {
            let base = preference.split(separator: "-").first.map(String.init) ?? preference
            if let language = languages.first(where: {
                $0.runtimeCode.caseInsensitiveCompare(base) == .orderedSame
            }) {
                return language.runtimeCode
            }
        }
        return languages.first(where: { $0.runtimeCode == "ru" })?.runtimeCode
            ?? languages.first?.runtimeCode
            ?? ""
    }
}

private extension InstallerCopy {
    static let fallback = InstallerCopy(
        windowTitle: "Языки VN Revival для The Murder of Sonic the Hedgehog",
        selectLanguageTitle: "Выберите язык",
        preparingTitle: "VN Revival",
        installingTitle: "Установка 30 языков",
        readyTitle: "Готово",
        failedTitle: "Установка не выполнена",
        selectLanguageMessage: "Все 30 локализаций будут установлены вместе. Выбранный язык станет активным.",
        languagePickerLabel: "Язык игры",
        preparingMessage: "Подготовка…",
        findingGameMessage: "Поиск Steam-версии игры…",
        gameNotFoundMessage: "Steam-версия игры не найдена. Выберите её папку вручную.",
        chooseGameTitle: "Выберите игру",
        chooseGameMessage: "Выберите папку игры в steamapps/common или приложение The Murder of Sonic The Hedgehog.app.",
        chooseGamePrompt: "Выбрать",
        installingMessage: "Проверка и установка всех языков VN Revival…",
        installedMessage: "Все 30 языков установлены",
        launchingMessage: "Запуск игры через Steam…",
        steamFailedMessage: "Не удалось открыть Steam. Запустите игру из библиотеки Steam.",
        installationErrorMessage: "Установка не завершена.",
        payloadNotReadyMessage: "Steam-версия игры найдена. Полный пакет из 30 языков ещё не готов для установки.",
        installButton: "Установить",
        changeLanguageButton: "Сменить язык",
        launchButton: "Запустить игру",
        chooseGameButton: "Выбрать игру…",
        retryButton: "Повторить",
        waitHint: "Это может занять несколько минут"
    )
}
