# Source-only archival

Keep final authored overlays, glossary/source inventory, fonts/licenses, native source and rebuild tools. Generated binary payloads are pinned to accepted installers instead of retaining duplicate payload/font trees locally.

## Restore and build

```sh
python3 -B Scripts/restore_archival_inputs.py
zsh Scripts/build-app.sh
zsh Scripts/build-windows-installer.sh
```

Both normal builders automatically restore their missing payload first. Requires Swift 6/macOS Command Line Tools, Python 3.9+, MinGW-w64 and the image/resource tools declared in those scripts. `archival-inputs.json` pins both release archives and all 214 extracted files; authenticated cold restoration reproduced all hashes. Both normal builds passed on 2026-11-03 (`sonic-macos-build`, `sonic-windows-build`) with these identical inputs.

Public release `release-0.2.1-e8eba473d34a` in `Master1C8/the-murder-of-sonic-the-hedgehog-localization` retains the accepted installers and compact evidence. `ARCHIVAL-EVIDENCE.json` indexes detailed historical audit data and extracted image references in Git revision `82cf5dd277cea0e25a0a1cf7ebb3e91cd420a9a7`. Inspect them with `git show REV:path` or restore exact prerequisite paths before using an older full Unity-patch recipe. Changed game patches also require the matching original installed game; GitHub does not redistribute the game.

After verification remove restored LocalizationPayload directories, `.build/`, `.build-app/` and `dist/`. Keep authored overlays, glossary, editable fonts/assets, source inventories, current tools and Git metadata. A rebuild does not imply new runtime acceptance or deployment.
