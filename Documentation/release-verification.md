# Published release verification

Windows and universal macOS packages were published on October 20, 2026.
Download the platform ZIP, evidence ZIP and `PUBLICATION-SHA256SUMS` from
[the published release](https://github.com/Master1C8/the-murder-of-sonic-the-hedgehog-localization/releases/tag/release-0.2.1-e8eba473d34a).

Compare each downloaded ZIP against its checksum line using `shasum -a 256`
on macOS or `Get-FileHash <file> -Algorithm SHA256` on Windows. If all ZIPs
are downloaded, `shasum -a 256 -c PUBLICATION-SHA256SUMS` verifies the full set.

```text
059065cb20c38338fb821aac8fae2363d15e1446db5f9ea38805ea289388f4cf  Sonic-Installer-Windows-0.2.1.zip
b4b0d8cfbb81fa6ce9bbcb197bef5c891a93c4b3ccb89fdc8d7c2b6ae311a3fc  Sonic-Installer-macOS-0.2.1.zip
1f0c10863ac5356f8e7faefaa3af6a13f34b9739dac71b4adb5fa98fca82c1a1  Sonic-0.2.1-e8eba473d34a-evidence.zip
```

Actual build source: [`e8eba473d34a2595b020d383c998469741b74a2e`](https://github.com/Master1C8/the-murder-of-sonic-the-hedgehog-localization/commit/e8eba473d34a2595b020d383c998469741b74a2e).
Match it with the tag, `provenance.json` and each installer ZIP's root
`vnrevival-release.json`; do not substitute the latest repository HEAD.
The source listing, build log and material hashes identify the compilation
and recorded test boundaries.

Locally built Windows x86-64 and universal Apple Silicon / Intel macOS installers (macOS 14+).
Actual source commit: `e8eba473d34a2595b020d383c998469741b74a2e`.

Download the platform installer, `Sonic-0.2.1-e8eba473d34a-evidence.zip` and `PUBLICATION-SHA256SUMS`.
Compare SHA-256, then inspect `provenance.json`, the platform manifest and the installer
ZIP's root `vnrevival-release.json`. They must identify this release tag's exact source
commit. `source-tree.txt`, `build.log` and `payload-materials.json` record compilation,
24 Python checks (one explicit skip), 18 native installer tests and both complete
30-language payload checks. Every ZIP entry was compared against its final stage.

The missing local Windows payload was restored from the exact verified published
archive, not regenerated through translation services. Its retained origin record
identifies those bytes without assigning a source commit to the previous binary.
No new real-game playthrough is claimed. macOS has an ad hoc signature, without
notarization. This is an unsigned local build statement, not a GitHub build
attestation or independent security review.

Historical build records retain their original dates and statuses. Earlier
archives without a retained build record keep unknown exact source provenance.
