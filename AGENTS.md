# Project instructions

This repository contains the unified 30-language VN Revival installer for The
Murder of Sonic the Hedgehog. Before localization or packaging work, read
the workstation localization instructions and the `vn-game-app` workflow.

- The supported macOS baseline is Steam build `20535215`, game version `1.01`.
- Detect the game through Steam `libraryfolders.vdf` and
  `appmanifest_2324650.acf`; a manually selected folder must still be tied to
  that manifest and App ID `2324650`.
- Never use the French fan translation as source text for any locale or ship
  any of its files. It is technical research only.
- One build installs all 30 non-English VN Revival locales. Never add a
  language picker to the installer; language selection belongs inside the game.
- Do not mark a language `ready` until its complete package is reviewed. Do not
  mark `payloadReady` true until all 30 languages, every payload file, and every
  SHA-256 are final.
- Every translation review must include a character-gender pass. For `ru`,
  `uk`, `pl`, `cs`, `bg`, `sr`, `es`, `es-419`, `pt-BR`, `fr`, `it`, `ro`,
  `de`, `el`, `ar`, `he`, and `hi`, check every known-gender speaker and
  reference for inflected verbs, adjectives, participles, titles, professions,
  and role nouns. For all other supported locales, check lexical feminine
  forms, pronouns, honorifics, kinship/address terms, and gendered speech
  markers where the language uses them. Never bulk-replace a masculine form:
  verify the actual referent and scene context first.
- Locale editorial acceptance follows the universal workstation protocol in
  `/Users/antonkrutov/.codex/instructions/game-localization-audit-workflow.md`.
  `Documentation/Localization/AUDIT_WORKFLOW.md` supplies only this game's
  pinned inputs, regression surfaces, and commands; it is not an exception or
  an alternative acceptance algorithm. The sole exception is the
  owner-authorized, one-use character-metadata migration
  `SONIC-CHARACTER-GLOSSARY-MIGRATION-2026-09`, defined in
  `Documentation/Localization/GLOSSARY_AMENDMENT_EXCEPTION.md`. It preserves
  prior semantic coverage only through that document's bounded impact and
  immutable amendment procedure; it grants no broader glossary exception.
  Do not claim that a sample, search, validator, or unchanged percentage is
  the complete semantic audit.
- Never weaken original-file, payload-file, ownership, staging, backup, or
  rollback checks to make an incomplete payload install.
- Do not open the built app for inspection: it starts installation immediately.
- Safe tests must use temporary fake game folders.
- A release build must contain the completed unified 30-language payload. A development
  build may keep the explicit not-ready payload and must fail before touching
  the game.
- Do not modify installed game files or launch the game during development
  without explicit permission.
