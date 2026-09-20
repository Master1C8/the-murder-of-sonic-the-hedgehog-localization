# Localization payload

This directory contains the verified text-and-font runtime payload for all 30
VN Revival locales. `Base/ru` stores deltas from the pristine Steam build;
`Locales/<code>` stores the second-stage deltas and complex-script helper DLLs.
`Tools/xdelta3` is the universal arm64/x86_64 decoder used transactionally by
the installer.

Localized image textures are intentionally deferred. `BuildManifest.json`
records `imagesModified: false`, and the original English PNGs remain intact.

Regenerate this directory only with `Scripts/build-unified-payload.py`; the
script verifies every delta by reconstructing the target file and checking its
SHA-256 before replacing this directory and marking the package ready.
