// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MurderOfSonicLocalizationInstaller",
    platforms: [.macOS(.v14)],
    products: [
        .executable(
            name: "MurderOfSonicLocalizationInstaller",
            targets: ["MurderOfSonicLocalizationInstaller"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "MurderOfSonicLocalizationInstaller",
            resources: [
                .copy("Resources/PackageConfig.json"),
                .copy("Resources/LocalizationPayload"),
            ]
        ),
        .testTarget(
            name: "MurderOfSonicLocalizationInstallerTests",
            dependencies: ["MurderOfSonicLocalizationInstaller"]
        ),
    ]
)
