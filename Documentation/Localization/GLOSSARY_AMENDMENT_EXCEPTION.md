# One-time character-glossary amendment exception

## Authorization and identity

- Exception ID: `SONIC-CHARACTER-GLOSSARY-MIGRATION-2026-09`.
- Status: `consumed`; completed on 2026-09-19. The pre-migration state is
  frozen in `glossary-amendment-freeze.json` and the immutable review evidence
  is under `GlossaryAmendment/cycle-1` through `cycle-9`.
- Authorized by the owner as a one-time exception for *The Murder of Sonic the
  Hedgehog* only.
- Steam build: `20535215`; game version: `1.01`.
- Canonical game slug: `the-murder-of-sonic-the-hedgehog`.
- Pre-migration canonical glossary source SHA-256:
  `6585d55f77a0e23e98e946376318305d91234e7b7b9e212a45b42331ae08673f`.
- Pinned source-units SHA-256:
  `7c3cbc60eec5570d4b07c2f3b44da2abec3173158df4a4c181c7014aaa8dd2af`.

This authorization preserves already completed glossary and game-text work
only under the bounded procedure below. It does not authorize publication,
deployment, changing locale readiness, launching the game or installer, or
editing installed game files.

## Allowed migration scope

The exception may be consumed once to bring this game's existing canonical
glossary into compliance with the character-context rules introduced after
localization work had already started. The migration may:

- place the player-character entry first while retaining its stable ID;
- add a missing speaking-character entry with a new stable ID;
- add or correct only a speaking character's translation-facing grammatical
  category: `male`, `female`, or player-only `hidden`;
- add concise, evidence-backed age, nationality or cultural background,
  manner-of-speech, identity, pronoun, or similar context when it materially
  affects translation;
- add exact research evidence to the established glossary source notes;
- reorder localized glossary layers mechanically to match the approved source
  order and translate only newly added or changed character material.

Existing stable IDs must not be renamed or deleted. Existing non-character
entries and character terms must not change. A character `meaning` may change
only by the minimum wording required for the information above; unrelated
rewriting is outside this exception.

## Required pre-migration freeze

Before editing the canonical glossary, record immutable copies or hashes of:

- the old canonical source and every localized glossary layer;
- every existing locale audit and its manual, derived and image artifacts;
- the ordered source and localized glossary ID lists;
- the speaking-character roster and the evidence used for every category;
- all currently accepted locale statuses.

The exact source diff must be classified by character ID and allowed change
type. Any unclassified change stops the migration.

## Bounded glossary review

The ordinary two-clean-full-audit rule is replaced only for this migration by
the following amendment review:

1. Review the complete canonical speaking-character roster and all changed or
   added character entries against the game and authoritative evidence.
2. For each localized glossary layer, review every changed or added character
   entry against the approved source, plus all glossary entries that refer to
   those characters or depend on their grammatical category or context.
3. Independently review that exact dependency set. Apply corrections and use
   immutable delta cycles until one cycle is clean on unchanged hashes.
4. Run the full structural glossary gate across all entries and locales: exact
   IDs and order, no missing, extra or empty values, valid schema and Unicode,
   and the repository glossary test suite.

Unchanged glossary entries retain their prior editorial evidence. This does
not make mechanical reordering a semantic change.

## Bounded game-text review

An accepted locale does not lose its prior complete semantic coverage solely
because this migration changes the glossary fingerprint. For every affected
character and locale, build an immutable impact closure containing:

- every line spoken by the character;
- every explicit reference to the character, including names, pronouns,
  titles, professions, roles, kinship or address terms and agreement-bearing
  forms;
- enough neighboring exchange context to resolve the real referent;
- exact repetitions, callbacks, runtime-composed fragments and glossary-linked
  wording affected by the new evidence;
- the project's complete mandatory regression catalog.

A qualified reviewer must read every row in that closure against the source,
the amended glossary and scene context. An independent reviewer then checks
the complete first closure. Corrections use the normal immutable delta formula:

```text
corrected IDs
+ (current closure IDs - previous closure IDs)
+ previously reviewed IDs whose evidence was explicitly invalidated
```

After a clean delta, rerun the full deterministic locale gate and append a
glossary-amendment record to the existing audit. The record must contain the
old and new glossary fingerprints, affected character IDs, exact glossary and
game-text review sets, list hashes and newline conventions, artifact hashes,
findings, regression result, validators and remaining inherited issues. Never
rewrite the historical audit as if it used the amended glossary originally.

## Restart boundary

This exception is void for an affected locale, and the normal full-audit rule
applies, if any of the following occurs:

- a stable ID is renamed or removed;
- a term or non-character meaning changes;
- character wording changes beyond the narrowly allowed metadata/context;
- game source text, inventory, extraction, alignment, runtime binding or
  stable-ID mapping changes;
- the complete affected glossary or game-text set cannot be enumerated
  deterministically;
- an audit artifact, old fingerprint, closure list or required hash is missing
  or unverifiable;
- review reveals a systemic issue that cannot be bounded to stable IDs.

## Consumption and expiration

The exception is consumed only after the repository source migration, all
affected localized glossary amendments, every required game-text amendment,
independent reviews and final validators are complete on one unchanged new
glossary fingerprint. At that point, change `Status` to `consumed`, record the
new canonical fingerprint and completion date, and do not reuse this procedure
for another glossary change.

Canonical-source publication remains a separate, explicitly authorized
operation through the protected VN Revival CLI and its dry-run, reviewed plan,
backup and apply safeguards.

### Consumption record

- Completion date: 2026-09-19.
- New canonical glossary SHA-256:
  `7c7921e245e6833398acb129797248785298dfbec935370752fff8c742448145`.
- Protected SiteForMods source commit: `d55e0e0` (`main`, local only).
- Final clean game-text/image-plan cycle: `GlossaryAmendment/cycle-9`.
- Accepted locales: `ar`, `cs`, `de`, `es`, `es-419`, `fa`, `hu`, `id`,
  `it`, `ja`, `nl`, `pt-BR`, `th`, `uk`, and `vi`.
- No glossary publication, site deployment, installed-game edit, game or
  installer launch, readiness change, or payload-readiness change occurred.
- Runtime and visual QA were not run and are not implied by this static
  editorial completion.
