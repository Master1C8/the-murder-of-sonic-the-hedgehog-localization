# Technical research: ChaosTrad French patch 1.0

Research date: 2026-09-17. This document records installation and packaging
facts only. French wording and payload files are not translation sources and
are not included in this repository.

## Public sources

- Project page: <https://chaostrad.fr/projects/tmosth>
- Installation guide and package description:
  <https://www.planete-sonic.com/communaute/fan-games/article/murder-of-sonic-le-patch-de-traduction-fr>
- Steam App ID: `2324650`.

The public guide identifies Windows, macOS, and Steam Deck packages. Windows
auto-detection uses the Steam folder and otherwise asks the player to select
the directory containing `The Murder of Sonic The Hedgehog.exe`. The macOS
package auto-detects the Steam installation. Manual Windows/Steam Deck
installation copies the patch over the game tree. Uninstallation is delegated
to Steam file verification.

## Manual Windows archive inspected

- File: `LMdSonic_install_manuelle.zip`
- Patch version: `1.0` (October 2023)
- SHA-256: `ca144fe358e77b05d75745d91f44f6652ac7eb89e472642479af9815a10e0919`
- Archive entries: 14
- Uncompressed size: 335,958,888 bytes

Payload surfaces:

```text
The Murder of Sonic The Hedgehog_Data/fr_version
The Murder of Sonic The Hedgehog_Data/level0
The Murder of Sonic The Hedgehog_Data/Managed/Assembly-CSharp.dll
The Murder of Sonic The Hedgehog_Data/sharedassets0.assets
The Murder of Sonic The Hedgehog_Data/StreamingAssets/aa/catalog.json
The Murder of Sonic The Hedgehog_Data/StreamingAssets/aa/StandaloneWindows64/defaultgroup_assets_all_*.bundle
The Murder of Sonic The Hedgehog_Data/StreamingAssets/aa/StandaloneWindows64/inventoryitems_assets_all_*.bundle
titlecard.png
```

The guide additionally states that the patch changes all dialogues, UI text,
text-bearing images, six fonts, layout/spacing, embedded code strings, text
dependent behavior, keyboard mappings, dynamic button sizing, locale-related
visual bugs, French grammar/date behavior, and the player-name length limit.

## Consequences for the VN Revival multi-language installer

1. The original game has no demonstrated independent language-pack interface.
   The observed patch replaces Unity data and code; it does not prove that a
   second selectable locale can be registered.
2. Addressables bundle names are content- and platform-dependent. Windows
   bundle names from the French archive must not be reused on macOS.
3. Copy-over installation without hashes can overwrite another fan patch. The
   VN Revival installer therefore requires exact original and payload SHA-256,
   refuses unknown current files, keeps a verified original backup, and uses a
   recoverable transaction.
4. Steam verification is a useful recovery fallback but not sufficient as the
   installer's only rollback mechanism.
5. A complete 30-language payload needs new runtime language activation plus
   code, font, image, Addressables catalog, bundle, and layout changes in
   addition to dialogue text. The installer records the selected runtime code;
   the French replacement patch does not provide code that can apply it.

## Installed macOS baseline inspected read-only

- Steam build: `20535215`
- Game version: `1.01`
- Unity: `2021.3.9f1` (`ad3870b89536`)

Observed original-file SHA-256 values:

| Relative to `Contents/Resources/Data` | SHA-256 |
| --- | --- |
| `level0` | `1e1ecff0c6762585c7633da91ad07bf7c168f1d6118c0c483de6501f33ad802d` |
| `Managed/Assembly-CSharp.dll` | `7e4ce2a6694461804b48396284b05e5d5a648ef134b317f37c2a3e368eb759ad` |
| `sharedassets0.assets` | `ab710a2f78acb227161af5b724682727914dda3b83a809e3ae3e0a9e7afda3a4` |
| `StreamingAssets/aa/catalog.json` | `222f4ef66002e99102d278c2109a7d2645e187bef07e3416bee58a0f30a585fb` |
| `StreamingAssets/aa/StandaloneOSX/defaultgroup_assets_all_4d829fc9da7ab64c374ae5aebaeeafd8.bundle` | `34e388f7502b72d6a3ac00445c6c8ffcf4a42edb1c137c31eefbb03b427cfdfb` |
| `StreamingAssets/aa/StandaloneOSX/inventoryitems_assets_all_99d768e0da67f575e33404b5acc31e43.bundle` | `a25d5cc0fb886a05c9fdebef436aa767c82ba1270f1255f1ad03e8d67fc1e758` |

These values are research evidence, not a license to set `payloadReady=true`.
The final manifest must be derived from the actual completed 30-language
payload and include every added, replaced, or retired file.
