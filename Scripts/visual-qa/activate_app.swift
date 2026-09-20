import AppKit
import Foundation

guard CommandLine.arguments.count == 2 else { exit(2) }
let bundleIdentifier = CommandLine.arguments[1]
guard let application = NSRunningApplication.runningApplications(
    withBundleIdentifier: bundleIdentifier
).first else { exit(3) }
guard application.activate(options: [.activateAllWindows]) else {
    exit(4)
}
