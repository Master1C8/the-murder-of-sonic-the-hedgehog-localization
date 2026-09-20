# Installer checkpoint

- Project: `/Users/antonkrutov/Desktop/The Murder of Sonic the Hedgehog Localization` on canonical `main`.
- Target: Steam App ID `2324650`, build `20535215`, game `1.01`, Unity `2021.3.9f1`.
- Coverage: all 30 canonical non-English VN Revival locales are editorially accepted and packaged with their prepared fonts. Each locale contains 3,547/3,547 translated text units with no missing runtime IDs.
- Selection: the user chooses the active locale in the installer. One application bundle contains all 30 variants; rerunning it safely switches the installed locale.
- Payload: one Russian base delta from verified pristine files plus per-locale xdelta layers. Complex-script locales also include their locale-specific helper DLL. The installer verifies original, artifact, and reconstructed output SHA-256 values before a transactional replacement.
- Safety: Steam library and manifest discovery, App ID/build validation, permanent original backup, ownership checks, staging, recovery, and rollback remain mandatory.
- Images: localized textures are deliberately deferred by owner instruction. `BuildManifest.json` records `imagesModified=false`; the ten text-bearing PNGs remain original English assets.
- Provenance: the French fan patch remains research-only and none of its files or wording are shipped.
- Release gate: `Scripts/release-audit.sh` validates all 30 locale manifests and payload artifacts, runs Python and Swift fake-folder tests, builds a universal arm64/x86_64 app, and verifies its signature.
- Runtime/visual status: static payload reconstruction is verified for every file. Full multilingual in-game visual QA remains a separate future stage and is not claimed here.
