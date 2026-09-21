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

extension InstallerCopy {
    static let fallback = InstallerCopy(
        windowTitle: "VN Revival Languages for The Murder of Sonic the Hedgehog",
        selectLanguageTitle: "Choose a Language",
        preparingTitle: "VN Revival",
        installingTitle: "Installing Localization",
        readyTitle: "Ready",
        failedTitle: "Installation Failed",
        selectLanguageMessage: "This build includes 30 localizations. Choose the language to apply to the game.",
        languagePickerLabel: "Game Language",
        preparingMessage: "Preparing…",
        findingGameMessage: "Looking for the Steam version of the game…",
        gameNotFoundMessage: "The Steam version of the game was not found. Select its folder manually.",
        chooseGameTitle: "Choose the Game",
        chooseGameMessage: "Select the game folder in steamapps/common or The Murder of Sonic The Hedgehog.app.",
        chooseGamePrompt: "Choose",
        installingMessage: "Verifying and installing the selected VN Revival localization…",
        installedMessage: "Localization installed",
        launchingMessage: "Launching the game through Steam…",
        steamFailedMessage: "Could not open Steam. Launch the game from your Steam library.",
        installationErrorMessage: "Installation did not complete.",
        payloadNotReadyMessage: "The Steam version of the game was found, but the complete 30-language package is not ready to install.",
        installButton: "Install",
        changeLanguageButton: "Change Language",
        launchButton: "Launch Game",
        chooseGameButton: "Choose Game…",
        retryButton: "Retry",
        waitHint: "This may take a few minutes"
    )
}
