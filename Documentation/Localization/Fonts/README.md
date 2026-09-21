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

All nine base prepared fonts contain U+0020 with a positive advance. Their exact
source URLs, source and output SHA-256 values, byte sizes, merge recipes, and
the pinned FontTools version are in
`LocalizationAssets/Fonts/manifest.json`. The files are distributed under
SIL Open Font License 1.1; the bundled license is
`LocalizationAssets/Fonts/OFL-1.1.txt`.

## Complex-script preparation

Arabic, Persian, Hebrew, Hindi, and Thai additionally use deterministic
locale-specific fonts under `LocalizationAssets/Fonts/Complex`. The build tool
shapes the exact accepted corpus with HarfBuzz 12.1.0 through uharfbuzz 0.51.7,
maps positioned glyph instances into the BMP private-use area, and preserves
recognized TMP rich-text tags byte-for-byte. Angle-bracketed visible actions
are deliberately treated as text, not as generic markup.

The corresponding `*.shaping.json` files pin the logical-to-shaped strings,
script-span fallback map, glyph metrics, source hashes, prepared-font hashes,
and RTL mode. Authored overlays remain logical and unchanged. At payload build
time, serialized UI text is pre-shaped; a locale-specific
`Managed/VNRevival.TextShaper.dll` shapes dynamic TMP text and sets RTL for
Arabic, Persian, and Hebrew. All 28 `TMP_Text.set_text` calls in the pinned
assembly are redirected, while the four `TMP_InputField.set_text` calls remain
untouched.

Rebuild the complex outputs with:

```sh
PYTHONPATH=/private/tmp/sonic-shaping-tools:/private/tmp/sonic-font-tools \
  python3 Scripts/prepare-complex-script-fonts.py \
  --localization-root Documentation/Localization \
  --font-root LocalizationAssets/Fonts \
  --output LocalizationAssets/Fonts/Complex
```

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

Full isolated Arabic and Hindi payloads were also built from the verified
original backup. Read-back verified both embedded shaped fonts, all 82 scene
texts, all 54 Addressables texts, Arabic RTL flags, Hindi LTR flags, the
embedded shaping resource, and 28/28 managed redirects with zero remaining
direct `TMP_Text.set_text` calls. The generated complex-font directory was
rebuilt independently and compared byte-for-byte.

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

Complex locales additionally require, for example:

```sh
  --font LocalizationAssets/Fonts/Complex/NotoSansArabicLatin-ar-Shaped.ttf \
  --shaping-map LocalizationAssets/Fonts/Complex/ar.shaping.json
```

## Current gate status

Static complex-script preparation passes for all five affected locales, and
the three RTL locales (`ar`, `fa`, and `he`) have completed fresh six-screen
runtime visual QA. Their dialogue route reaches the evidence inventory and
rings minigame without animation stalls; mixed Latin runs, punctuation, and
edge whitespace remain correctly separated, and the diagnostic THINK splash
fits on one line in each locale.

Every managed locale assembly also contains one structurally verified shared
text-animation completion guard, so invisible final TMP characters cannot
leave dialogue animation active indefinitely. The complete unified payload is
ready for all 30 locales and `payloadReady=true`. Texture translation is
intentionally deferred by owner scope; the release records
`imagesModified=false`.
