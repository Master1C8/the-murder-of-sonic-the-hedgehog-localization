# Cycle 1 independent amendment review

Date: 2026-09-19  
Reviewer: independent Codex reviewer (`Maxwell`)  
Result: corrections required; cycle 1 is not accepted.

## Verified clean

- Canonical source: 117 entries; 30 localized layers with 117 entries each.
- `barry` is first and retains stable ID `barry`.
- No stable ID, character term, non-character meaning, or pre-existing
  localized prose changed.
- The expected 16 canonical and 480 localized controlled metadata suffixes are
  present.
- All 55 frozen artifacts match their recorded hashes: 45 accepted-locale
  manual/overlay/image-plan artifacts and 10 audit JSON artifacts.
- All 15 accepted overlays validate at 3,547/3,547 units and recompile
  byte-identically.
- Historical audits remain compatible evidence, but do not replace the new
  amendment review required by the exception.

## Findings

1. The required primary and independent semantic reads of every row in the
   3,547-ID closure and all 10 image plans have not been completed. Cycle 1
   cannot consume the exception without them.
2. Fourteen of the sixteen category assignments have adequate evidence.
   `the-train` does not: the English corpus consistently uses `it/its` and
   supplies no masculine or feminine self-reference or address. Existing
   target layers also demonstrate noun-sensitive agreement (for example,
   feminine in Hindi and neuter in Greek), so `male` is not a universal fact
   recoverable from the source.
3. `cubot` needed a precise official citation rather than identity alone. The
   source notes were subsequently expanded with exact game IDs and official
   SEGA material, including Cubot's masculine-coded `ボクら` self-reference.
4. The glossary workflow test suite had one stale heading assertion. The test
   and the contradictory onboarding paragraph were subsequently synchronized
   with the canonical grammatical-category contract; the focused suite now
   passes 39/39 and the complete SiteForMods suite passes.

No game-text, locale readiness, installed-game, runtime, publication, or
production state changed during this review.
