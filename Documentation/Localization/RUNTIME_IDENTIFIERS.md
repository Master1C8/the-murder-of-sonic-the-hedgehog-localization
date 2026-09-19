# Runtime identifier localization standard

This contract applies to every locale of The Murder of Sonic the Hedgehog.
Runtime identifiers and control syntax are immutable. A locale may translate
only the display value associated with an identifier.

## Protected values

- Ink speaker keys before `::`, including `Barry`, `Conductor`, and `Train`.
- Ink command names and syntax, including `>>>>`, command names, parentheses,
  separators, variable names, and branch/control tokens.
- Compiled Ink string operands used by `==`, `VAR=`, or `temp=` operations.
  These values remain byte-exact even where historical corpus compatibility
  keeps their stable IDs in locale files.
- Managed-code literals used by comparisons, lookups, portrait selection,
  font selection, Addressables, events, or save-state logic.
- Asset keys, IDs, paths, hashes, field names, and locale-independent markup.

Never make a protected value translatable merely because the same English
word is visible somewhere in the game. Code usage determines whether a literal
is control data.

## Display-only localization

- Character labels use `runtime:speaker:<runtimeKey>` units. The overlay
  supplies the displayed name, while `runtimeKey` remains English. The managed
  patch redirects only the final `nameTagText` assignment through this mapping.
- `Barry` is not a display-label unit. The original `Barry` comparison must
  remain intact so the game substitutes the player-entered name and selects the
  protagonist portrait. `NamelessMC` remains the hidden-speaker sentinel.
- Establishing-shot titles expose only the argument of
  `>>>>EstablishingShot(<title>)`. Reinsertion reconstructs the original command
  shell and replaces only `<title>`.
- Ordinary dialogue exposes only the body after `Speaker::`; reinsertion keeps
  the exact source speaker key and `::` separator.
- Save-slot location labels use a display-only mapping after the game converts
  `GameState.environment` to a readable string. Runtime keys such as `Library`,
  `Conductor_Car`, and `LockdownDiningCar` remain unchanged in code and save
  data; only the final text assigned to `SaveFileView._locationName` is mapped
  to an existing localized UI value. The mapping must cover all 13 environment
  keys exposed by the game's debug map, including the exact double spaces that
  the original `SplitCamelCase`/underscore sequence produces for
  `Conductor_Car` and `Final_Push`. The three dining-car variants intentionally
  share one display label. This mapping is mandatory for every locale and must
  fall back to the original display string for unknown environments.

## Required gates for every locale

1. No `managed-runtime-control` entry may appear in a locale overlay.
2. Every speaker display-label and establishing-shot title must have a locale
   value before that locale can be ready.
3. Story reinsertion must prove that speaker prefixes and command shells are
   unchanged.
   `runtime-exact-values.json` is the machine-readable source of truth for
   compiled Ink operands and historically exposed inline speaker prefixes;
   source validation, overlay compilation, overlay validation, story
   reinsertion, and development-patch construction must reject violations.
4. Managed-patch verification must prove that the original `Barry` and `Train`
   comparisons remain and that only the name-tag display path calls the locale
   mapping.
5. Test only derived payloads or temporary fake game trees during development;
   installation and runtime QA require their own explicit authorization.
6. Managed-patch verification must prove that environment keys and save
   files are unchanged and that only the final save-slot location display path
   calls the locale mapping.

These rules are enforced by `Tests/test_localization_pipeline.py` and are part
of `Scripts/release-audit.sh`.
