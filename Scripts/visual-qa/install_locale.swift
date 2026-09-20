import Foundation

@main
struct VisualQAInstallLocale {
    static func main() throws {
        guard CommandLine.arguments.count == 4 else { throw UsageError() }
        let runtimeCode = CommandLine.arguments[1]
        let configURL = URL(fileURLWithPath: CommandLine.arguments[2])
        let payloadURL = URL(fileURLWithPath: CommandLine.arguments[3], isDirectory: true)
        let config = try PackageConfig.load(from: configURL)
        let core = InstallerCore()
        guard let installation = core.detectSteamInstallation(appID: config.steamAppID) else {
            throw InstallerError.invalidGameFolder
        }
        try core.install(
            payload: payloadURL,
            config: config,
            selectedRuntimeCode: runtimeCode,
            into: installation
        )
        let receiptURL = installation.root
            .appendingPathComponent(".vn-revival", isDirectory: true)
            .appendingPathComponent(config.packageID, isDirectory: true)
            .appendingPathComponent("receipt.json")
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let receipt = try decoder.decode(InstallationReceipt.self, from: Data(contentsOf: receiptURL))
        guard receipt.activeLanguage?.runtimeCode == runtimeCode else {
            throw VerificationError(expected: runtimeCode, actual: receipt.activeLanguage?.runtimeCode)
        }
        print("installed-and-verified \(runtimeCode)")
    }
}

private struct UsageError: LocalizedError {
    var errorDescription: String? {
        "Usage: visual-qa-install-locale <runtime-code> <PackageConfig.json> <LocalizationPayload>"
    }
}

private struct VerificationError: LocalizedError {
    let expected: String
    let actual: String?

    var errorDescription: String? {
        "Receipt verification failed: expected \(expected), got \(actual ?? "nil")"
    }
}
