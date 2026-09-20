# Localization font preparation

The pinned font set under `LocalizationAssets/Fonts` statically covers the
complete final corpus for all 30 non-English locales: every locale's 3,547
overlay values and 10 text-bearing image translations. The deterministic
result is recorded in `font-audit.json`; static coverage is 30/30 with no
missing rendered codepoints.

## Selected fonts

- Noto Sans Regular: Latin, Greek, Cyrillic, Vietnamese, and the other
  supported Latin-script locales.
- Noto Sans CJK SC, TC, JP, and KR: `zh`, `zh-TW`, `ja`, and `ko`.
- Reproducible Noto Sans composites: Latin plus Arabic, Hebrew, Devanagari,
  or Thai for `ar`/`fa`, `he`, `hi`, and `th`. The Latin component is retained
  so punctuation, digits, protected ASCII operands, and mixed-script content
  remain covered by the same dynamic source font.

All nine prepared fonts contain U+0020 with a positive advance. Their exact
source URLs, source and output SHA-256 values, byte sizes, merge recipes, and
the pinned FontTools version are in
`LocalizationAssets/Fonts/manifest.json`. The files are distributed under
SIL Open Font License 1.1; the bundled license is
`LocalizationAssets/Fonts/OFL-1.1.txt`.

Rebuild the prepared set from the verified upstream files with:

```sh
PYTHONPATH=/private/tmp/sonic-font-tools \
  python3 Scripts/prepare-localization-fonts.py \
  --source-dir /path/to/verified-noto-files \
  --output LocalizationAssets/Fonts
```

Re-run exact corpus coverage with:

```sh
PYTHONPATH=/private/tmp/sonic-font-tools \
  python3 Scripts/audit-localization-fonts.py \
  --localization-root Documentation/Localization \
  --font-root LocalizationAssets/Fonts \
  --output Documentation/Localization/Fonts/font-audit.json
```

## Reinsertion proof

`build-locale-patch` preserves the two stable Unity Font object IDs and
replaces their embedded source binaries before wiring the existing dynamic TMP
fallback assets. A complete Bulgarian development patch was built from the
verified original backup and read back successfully: both the scene and
Addressables source Font objects matched the selected Noto Sans SHA-256, all
3,547 translations were present, and the Addressables catalog was updated.
Separate read-back probes also preserved a merged Arabic/Latin TTF and the
16 MiB Simplified Chinese CJK OTF byte-for-byte. These are static reinsertion
proofs only; no installed game file was changed and the game was not launched.

Example isolated build:

```sh
PYTHONPATH=/private/tmp/sonic-font-tools \
  python3 Scripts/extract-localization-assets.py build-locale-patch \
  --data-root /path/to/verified/original/Data \
  --inventory Documentation/Localization/inventory.json \
  --overlay Documentation/Localization/bg.overlay.json \
  --font LocalizationAssets/Fonts/NotoSans-Regular.ttf \
  --font-name "VN Revival Noto Sans" \
  --output /path/to/empty/output
```

## Gates still open

Font cmap coverage and the presence of OpenType GSUB/GPOS tables do not prove
that TextMesh Pro applies complex shaping or the Unicode bidirectional
algorithm. Runtime shaping remains mandatory for `ar`, `fa`, `hi`, and `th`;
bidirectional layout remains mandatory for `ar`, `fa`, and `he`. TextMesh Pro
3.x exposes `ITextPreprocessor` specifically for preprocessing and shaping,
and the game contains no existing Arabic, Persian, Hebrew, bidi, or RTL helper.

Accordingly, `complexScriptShaping`, `bidirectionalLayout`, and
`runtimeReadability` remain `not-run`. No locale is marked `ready`, and
`payloadReady` remains `false` until those mechanisms and the later visual,
texture, packaging, and unified-payload gates pass.
