# Localization checkpoint

## Current 30-locale state — 2026-09-20

- Editorial acceptance is complete for all 30 supported non-English locales.
  Each final overlay contains the same 3,547 stable IDs and each locale has a
  completed 10-row text-bearing image plan. The glossary amendment is consumed
  and its final 30-locale state is included in the accepted artifacts.
- Static font preparation now passes 30/30 exact-corpus coverage. Nine pinned
  base Noto outputs cover every rendered codepoint across the 3,547 overlay
  values and 10 image translations per locale. Five deterministic
  HarfBuzz/PUA outputs additionally prepare Arabic, Persian, Hebrew, Hindi,
  and Thai shaping without changing the authored overlays. Sources, licenses,
  hashes, metrics, shaping maps, and recipes are recorded under `Fonts/` and
  `LocalizationAssets/Fonts/`.
- A generic isolated `build-locale-patch` path now embeds the selected font in
  both stable Unity source Font objects and retains the existing dynamic TMP
  fallback graph. A complete Bulgarian patch built from verified originals,
  and both embedded font binaries read back with the expected SHA-256. Separate
  merged Arabic/Latin TTF and Simplified Chinese CJK OTF probes also read back
  byte-for-byte. No installed game file was modified and the game was not
  launched.
- The complex-script payload path is implemented. Serialized UI is pre-shaped,
  Arabic/Persian/Hebrew serialized UI receives RTL state, and a per-locale
  `VNRevival.TextShaper.dll` redirects all 28 dynamic `TMP_Text.set_text`
  assignments while leaving four input-field assignments untouched. Isolated
  Arabic and Hindi builds passed font, text, direction, embedded-resource, and
  IL read-back checks. Runtime readability and visual layout remain `not-run`:
  neither the game nor the built installer was launched.
- Release state is intentionally unchanged: all locale declarations remain
  `ready=false` and `payloadReady=false`. Texture production, unified payload
  assembly, fake-folder installer verification, runtime/visual QA, and final
  release audit remain later stages.

- Game baseline: The Murder of Sonic the Hedgehog, Steam App ID `2324650`,
  build `20535215`, version `1.01`, Unity `2021.3.9f1`.
  The source installation is read-only input.
- Source fingerprint:
  `c85a1b00191894e5d42665322b8716c042536659ce939893bf7a59310dde2086`.
  The canonical source package contains 3,547 translatable units and has
  source-units SHA-256
  `7c3cbc60eec5570d4b07c2f3b44da2abec3173158df4a4c181c7014aaa8dd2af`.
- Corpus composition: 3,335 visible Ink units (including 6 display-only
  establishing-shot titles), 52 inventory fields, 54 confirmed Addressables
  UI strings, 82 confirmed scene UI strings, 7 confirmed managed-code UI
  strings, and 17 display-only speaker labels. The engineering inventory additionally
  records 73 default-group and 95 level0 UI candidates, 706 managed-string
  candidates, 72 PNG candidates, and 17 font/SDF assets.
- Canonical glossary: the Russian layer in SiteForMods remains unchanged and
  passed the 117/117 ID/order/empty-value check. Canonical source SHA-256:
  `6585d55f77a0e23e98e946376318305d91234e7b7b9e212a45b42331ae08673f`.
  Expected normalized Russian-layer fingerprint:
  `7dafe390281919b4106e3726186fdc70861002d4f4ba9bf6b5a0e553516fc668`.
- Russian text artifacts:
  - `ru.manual.json`: 3,549 authored entries — all 3,547 corpus units plus
    the two preserved technical `100%` display values
    (`unity:level0:1525:m_text` and `unity:level0:1542:m_text`).
    SHA-256: `3c795be0b07dc374e764458ba496027c1ce0a21c2f3541465bd4001c6812f9cb`.
  - `ru.overlay.json`: 3,547 compiled units, with no missing or extra IDs.
    SHA-256: `cf03a07849890d0891335239645ab135a74d4b86ceca7f98669af5338089c582`.
  - `ru.images.manual.json`: all 10 text-bearing images have source text,
    Russian text, context, glossary IDs where applicable, and status
    `translated`. SHA-256:
    `5b47d240dd37d4d4f2f561353bf0a911e6cc4c16a46ad7e1ae0c92b9025c3d98`.
- Source validation passed: 3,547 source units, 29 context batches, 3,547 CSV
  rows, all 72 PNG hashes, 72/72 image-review classifications, 10
  text-bearing images, and 15 preserve-exact-symbol candidates. The image
  candidate-set SHA-256 is
  `0083d052c4058280700c4e3dac67360463bfc90f44228bff7c9b3e3a926c485b`.
- Overlay compilation and work-in-progress validation pass with `missing: []`,
  `extra: []`, and `tokenErrors: []`. Strict validation remains failed because
  11 records are still marked `needs-review`: two pre-existing dialog/item
  defaults with Russian placeholder text and nine hierarchy-only `New Text`
  placeholders. Runtime evidence is required before reclassifying them; the
  validator was not weakened to hide them.
- Editorial state: the previous claim of two clean full audits was invalidated
  on 2026-09-17 after an independent review found objective semantic,
  grammatical, idiomatic, voice, punctuation, and consistency defects. A
  corrective pass has changed 85 authored entries and the overlay was rebuilt.
  The latest six corrections came from a complete targeted review of all 292
  Amy lines: three masculine first-person forms and three masculine renderings
  of her journalist role were changed to feminine agreement. The canonical
  Russian glossary still uses the base term `журналист-репортёр`; it was not
  changed as part of game-text editing.
  A subsequent complete targeted review covered all 155 Rouge lines and all 96
  Blaze lines, plus 60 lines in which either character is named. It corrected
  two masculine first-person forms for Rouge, two masculine self-references
  for Blaze, and one role-assignment line that described both women with
  masculine role nouns. Unrelated masculine agreement referring to male
  characters was preserved.
  One additional QA pass then checked the complete corpus mechanically for
  coverage, tokens, retained English, negation balance, repeated-source
  consistency, glossary names, punctuation anomalies, and suspicious length
  ratios; the Prologue was also reread fully against the English source, with
  targeted contextual review of the other affected scenes. This does not count
  as the complete semantic audit required by the current project workflow.
  The legacy clean-full-audit count was 0 / 2 when that rule applied. As of
  2026-09-18, future acceptance follows `AUDIT_WORKFLOW.md`; the current
  Russian candidate still needs its one complete semantic pass, followed by
  the dependency-aware diff and final machine gates.
- Image scope: all 10 source PNGs were visually inspected, but no PNG was
  edited, redrawn, or written back into a Unity bundle. The image JSON is a
  translation/redraw plan for the later texture stage; map symbols and the
  safe code `230401` remain marked for exact preservation.
- Development runtime state: on 2026-09-17 the owner explicitly authorized a
  Russian-only development install and launch against Steam build `20535215`.
  The hash-locked development payload reinserts 3,329 story units, 82 scene UI
  strings, 54 Addressables UI strings, 52 inventory fields, and 10 managed-code
  strings. It connects the bundled Liberation Sans source font as a dynamic
  Cyrillic TMP fallback to six shared scene-font assets and 14 Addressables
  font assets. The six replaced files have verified originals under
  `.vn-revival/dev-russian-runtime/original-backup`; installation and restore
  both passed first on a temporary fake Steam tree. No Texture2D or Sprite
  object changed, and no source PNG was written.
- Runtime findings: the first launch exposed a missing TextAsset alignment byte
  and was rejected by Unity; the serializer was fixed. The next visual sample
  loaded Russian story text but omitted Cyrillic glyphs because only the
  Addressables font copies had fallbacks; the exact five level0 font references
  were then identified and patched in `sharedassets0.assets`. An intermediate
  catalog rewrite shifted Addressables extra-data offsets and produced invalid
  bundle paths; catalog records now preserve their original byte lengths. The
  current build launches and its fresh `Player.log` contains no corruption,
  mismatch, invalid-path, exception, or failed-load lines. Final visual glyph
  confirmation of the corrected run remains pending.
- Runtime identifier correction: speaker prefixes, `Barry`/`Train` comparison
  literals, Ink command names, delimiters, and asset keys are now explicitly
  protected for every locale. Character names use 17 display-only mappings;
  the six `EstablishingShot` titles expose only their visible argument. A new
  Russian development payload was built and statically verified in a temporary
  original-data copy: 3,335 story units, 7 managed UI replacements, and 17
  speaker labels. Its IL retains the original English `Barry` and `Train`
  comparisons and redirects only `nameTagText` through the display mapping.
  On 2026-09-17 the owner explicitly approved installing this correction and
  launching the game. All six installed files matched the new payload SHA-256,
  the verified original backup was preserved, and Steam launch produced a
  running game process. The fresh `Player.log` contains no startup exception,
  failed load, corruption, mismatch, or invalid-path report. Visual confirmation
  of the corrected speaker and location labels remains `not-run`.
- Runner HUD layout correction: screenshot evidence showed that Russian
  `КОЛЬЦА` occupied about 229 px at the inherited 56-point fallback-font size
  inside a 200 px `RingsLabel`, forcing the last glyph onto another line. The
  locale now keeps the complete translation and stable unit ID while applying
  `m_fontSize=46` and `m_fontSizeBase=46` through the allowlisted
  `layoutOverrides` mechanism. A patch was built from verified originals in a
  temporary directory and read back as `КОЛЬЦА`, 46/46; all 3,547 units,
  protected tokens, and the layout schema validate. No image or installed game
  file was changed, and visual runtime confirmation remains `not-run`.
- Save-menu layout correction: screenshot evidence showed the runtime location
  and timestamp colliding inside a save slot. Locale-specific `level0` TMP
  overrides now reduce the location from 36 to 28 points and the timestamp
  from 24 to 18 points. The generated patch was compared with the previously
  installed Russian `level0`; only the two intended TMP objects and their four
  font-size fields differed. Installed-game and visual confirmation remain
  `not-run` for this revision.
- Save-slot location localization correction: screenshot evidence on
  2026-09-18 showed `Library` and `Conductor Car` remaining English while the
  special-cased `Dining Car` was Russian. `SaveFileView.UpdateInfoText` derives
  these labels from the protected `GameState.environment` key through `SplitCamelCase`,
  bypassing the translated scene fields. The shared managed patch now maps the
  final display string through existing localized UI values immediately
  before the two `_locationName` assignments (the special dining-car and
  general environment paths).
  Environment keys, serialized saves, Ink identifiers, and unknown-value
  fallback remain unchanged. This is the required mechanism for every locale;
  it adds no source units and therefore does not invalidate in-progress
  translations. A complete static audit then matched all 13 environment keys
  exposed by `DebugMapScreen` against all 11 unique strings emitted by the
  original save-menu formatting. It caught exact double-space outputs for
  `Conductor_Car` and `Final_Push`; the mapping now preserves and intercepts
  those exact values. The three dining-car environments intentionally converge
  on `Dining Car`. The corrected isolated payload is
  `/private/tmp/sonic-all-save-locations.N5tKHy`; it reports 11 unique
  `saveLocationDisplayLabels`, and its patched `Assembly-CSharp.dll` SHA-256 is
  `52abff93c821095e42572f0dc1193689a834cc1b61afefa89696142150205e3b`.
  Source validation, 3,547/3,547 overlay validation, and all localization
  pipeline tests pass. The payload was not installed; runtime/visual
  confirmation remains `not-run`.
- Release state is unchanged: the unified installer was not opened, the
  30-language payload remains incomplete, `payloadReady=false`, and all 30
  installer locale declarations remain `ready=false`. The Russian development
  payload is not a release artifact and must not be promoted to one.
- French fan localization was used only for technical research. No French
  wording or files were used as Russian source material.
- Next handoff: visually confirm Cyrillic glyphs in the corrected live dialogue,
  then inspect wrapping/clipping across dialogue, menus, inventory, and the
  runner UI. Complete the semantic, dependency-aware diff, regression, and
  final machine gates in `AUDIT_WORKFLOW.md`, and resolve or reclassify the 11
  technical records using runtime evidence. Localized texture production
  remains a separate later stage. Do not mark the locale or unified payload
  ready until those stages are complete.

## Five-locale Sol editorial audit group — 2026-09-18

- Scope: `es`, `es-419`, `pt-BR`, `ja`, and `de`, each audited independently
  by GPT-5.6 Sol high against the same 3,547-unit English source inventory and
  the locale's complete 117/117 canonical glossary layer. Each audit also read
  all 10 text-bearing image plans; no PNG, Texture2D, Sprite, installed-game
  file, source asset, or other locale was changed.
- Editorial gate: every locale completed a full corrective source-to-target
  pass and then two consecutive full clean passes over 3,547/3,547 units plus
  10/10 image plans on an unchanged final version. The passes explicitly
  covered canonical gender and ambiguity, Amy/Rouge/Blaze feminine forms,
  pronouns and agreement, titles/professions/feminatives or target-language
  analogues, character voice, meaning, humor, terminology, locations, and
  display-only labels. A finding during a clean attempt reset that locale's
  count and restarted both passes.
- Technical gate: the parent independently recompiled all five overlays to a
  temporary directory and byte-compared them with the checked files. All five
  report 3,547/3,547 units and zero missing, extra, token, or layout errors.
  `validate-source` passes with 3,547 source units, 29 batches, 3,547 CSV rows,
  72/72 image candidates reviewed, 10 text-bearing images, and 15
  preserve-exact-symbol candidates. The localization test suite passes 10/10.
  The only strict-validator findings are the same 11 inherited English source
  placeholders; `--allow-incomplete` is `ok=true` for all five locales.
- UI regression checks: all 13 DebugMap environment labels, 11 unique save-slot
  display labels (including the exact internal `Conductor  Car` and
  `Final  Push` forms), six establishing-shot titles, 17 speaker display
  labels, the runner Rings label, and save location/timestamp fields were
  reviewed. Runtime environment keys, serialized save values, Ink IDs,
  commands, placeholders, markup, paths, and `Barry`/`Train` comparison
  literals remain unchanged.
- Locale layout results: `es` uses Rings 44/44 and save location 24/24;
  `es-419` uses save location 28/28 and timestamp 18/18; `pt-BR` uses save
  location 22/22 and timestamp 18/18; `ja` needs no override; `de` uses save
  location 24/24 and timestamp 18/18. `ANILLOS` (`es-419`), `ANÉIS`, `リング`,
  and `RINGE` did not justify a Rings override. These are static/layout
  findings; runtime and visual QA remain `not-run` by instruction.
- Final SHA-256 (`manual`, `overlay`, `images.manual`):
  - `es`: `c0fb9930a52c153441e50b23610142a3fd63557dc9ad73d6c98efb885c40f9cc`,
    `0f2e3d6a9b7bfd4d9d2240972e96722ce2cadd65db05ae3b59257478ea02bb6d`,
    `5432ca390b4de5be500684e888b598ccf24329741edfaba071a24f4664a55bc9`.
  - `es-419`: `b29fb0ae674eb246a059971589f5cb3fccdac2cfa6e88698b3415ed9be860850`,
    `49ae0be91b12bd0e84b74bf30a32e54821f7b561ebe328637e2daaa1f0c0fdf7`,
    `83319545c72d364c03aa7e242d871fa9259d738848e5bf419ca368bb8803ab30`.
  - `pt-BR`: `79cb8087857130021a2fe9d4c74713551f509d770b5e4e9893c1a1bb20a4ce00`,
    `10c6325ff25d30690640483b43ab03702db2ed5019cbadbd2d54c6ac78fe3e8a`,
    `c3fd1d53ed6472e2aad9bf66df3f708db1eb87de1ade71b57a28d1bc62fb46d4`.
  - `ja`: `8d0e8adaf9fe38ce6b562cf1dd43a34f8c20df766e4ef823d20b62f909763829`,
    `cf5f3c32cf18c2179e1516d623d8a67c4a5fc19225e03d5791622a15df900720`,
    `42dd688d75d51f348878fa573acd344ddd3d6de0b6a4eb02f5f11451717a1802`.
  - `de`: `3474cccce3ccb4e5a2384e6ef823e1203f4a51ee296f69fbf9a855dd0a7745ce`,
    `43ee7ecf7e246d3c62b8b319d7596518f17f5e4c252257f714051e5781181e30`,
    `793840f10e890d84c6bc02e6bd056902f9afdd22c6c30883191cc0ab7e8c05a5`.
- Release state remains unchanged: the five audited locales and all other
  installer locale declarations remain `ready=false`; `payloadReady=false`.
  Editorial completion of these text layers does not establish font, texture,
  reinsertion, runtime, visual, unified-payload, or release readiness.

## One-time character-glossary migration authorization — 2026-09-19

- The owner authorized the one-use exception
  `SONIC-CHARACTER-GLOSSARY-MIGRATION-2026-09`; its authoritative scope and
  acceptance procedure are recorded in
  `GLOSSARY_AMENDMENT_EXCEPTION.md`.
- Status is `consumed`; the migration completed cleanly on 2026-09-19.
  `barry` is first with stable ID unchanged and owner-confirmed translation
  grammar `male`. The other fifteen speaking-character entries carry their
  controlled metadata; the Train uses translation grammar `male` while
  retaining canonical gender `none` and English `it/its` semantics. All 30
  localized glossary layers have exact 117-ID/order parity and the same
  sixteen controlled metadata suffixes.
- The exception is pinned to canonical glossary source SHA-256
  `6585d55f77a0e23e98e946376318305d91234e7b7b9e212a45b42331ae08673f`
  and source-units SHA-256
  `7c3cbc60eec5570d4b07c2f3b44da2abec3173158df4a4c181c7014aaa8dd2af`.
- The protected SiteForMods source change is committed locally on `main` as
  `d55e0e0`; it was not published or deployed. Publication remains separately
  authorized and was not requested.
- Pre-migration evidence is frozen in `glossary-amendment-freeze.json`; the
  immutable cycle-1 review set is under `GlossaryAmendment/cycle-1`. The new
  local canonical fingerprint is
  `7c7921e245e6833398acb129797248785298dfbec935370752fff8c742448145`.
  Structural checks report 117 source entries and 30 complete 117-entry locale
  layers with exact ID/order parity. The source ID-order SHA-256 is
  `a9792344171e033dc3d5d0aab0b532323128d5d2591bfb39399f15161720ff76`.
- The accepted locale set is exactly fifteen: `ar`, `cs`, `de`, `es`,
  `es-419`, `fa`, `hu`, `id`, `it`, `ja`, `nl`, `pt-BR`, `th`, `uk`, and
  `vi`. The complete amendment closure contains 3,547 text units (SHA-256
  `45286e54a5e8cc1339191d82af7eeee3b58456dccd0654049a238217ea41b77e`)
  and ten image plans (SHA-256
  `217e39c87ae32c6b2cf7ed3657e142e366a4b6f4f76f1a0f4e46f9f7661ed01c`).
- Immutable primary, independent, correction, and final-clean evidence is
  preserved in `GlossaryAmendment/cycle-1` through `cycle-9`. Cycle 9 is clean
  on the final hashes. Existing audits for `ar`, `cs`, `fa`, `hu`, `id`, `it`,
  `nl`, `th`, `uk`, and `vi` contain appended amendment records; this section
  is the amendment record for `de`, `es`, `es-419`, `ja`, and `pt-BR`, which
  had checkpoint-only historical acceptance evidence. Exact final
  manual/overlay/image-plan hashes for all fifteen locales are recorded in
  `GlossaryAmendment/cycle-9/artifact-hashes.json` (SHA-256
  `202460b1c5313843455bc97076a817d9f7eb902f892e489f2aead8678bff6d99`).
- Final validation is clean for all fifteen locales: 3,547/3,547 units, zero
  missing/extra/protected-token/layout errors, byte-identical rebuilt overlays,
  10/10 image plans, 49/49 raw Ink controls, 16/16 additional comparison
  literals, 25/25 exact ASCII `True` operands, and 5/5 exact
  `Conductor’s Wife:: ` prefixes. The same eleven inherited English source
  placeholders remain explicitly classified `needsReview`.
- Source validation passed; Python localization tests passed 10/10; Swift
  fake-folder installer tests passed 10/10. Runtime and visual QA were not run.
  No installed game files were edited and neither the game nor installer was
  launched.
- Locale `ready` values and `payloadReady` remain unchanged. The completed
  static editorial migration does not establish font, texture, runtime,
  visual, packaging, unified-payload, or release readiness.

## Unified text-and-font installer payload — 2026-09-20

- All 30 locale runtime variants were rebuilt from the verified pristine Steam
  build `20535215`. Every manifest reports 3,547/3,547 text units, no missing
  translation IDs, and the pinned locale font strategy.
- The compact payload uses one `ru` base xdelta chain from original files and
  per-locale deltas from that deterministic base. Every delta was decoded to a
  temporary file and byte-verified against the expected target SHA-256 before
  readiness changed.
- The installer now applies the selected locale transactionally, verifies all
  original/artifact/output hashes, and supports language switching by rerun.
  The universal bundled xdelta3 helper contains arm64 and x86_64 slices.
- All 30 language declarations are `ready=true`; `payloadReady=true`.
- Owner scope for this build explicitly defers texture translation. All ten
  image plans remain available, no PNG is modified, and the payload manifest
  records `imagesModified=false`.
- This establishes static text/font packaging readiness. It does not claim
  multilingual in-game visual QA, which remains a separate future stage.

## Verified legacy-development migration — 2026-09-20

- The release installer now recognizes the repository's earlier
  `.vn-revival/dev-russian-runtime` Russian development installation.
- Migration is deliberately narrow: the legacy receipt must contain exactly
  the final package's original-backed files, its original hashes must match the
  release manifest, the installed files must match every recorded patched
  hash, and all legacy backups must match the pristine original hashes.
- On an exact match, the verified pristine backups and ownership state are
  adopted before the normal transactional locale update. Any mismatch aborts
  without editing the installed game.
- Fake-folder coverage includes both successful migration and refusal of a
  tampered legacy installation.
