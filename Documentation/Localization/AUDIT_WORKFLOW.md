# Project audit profile

This file applies the universal game-localization editorial audit protocol at
`/Users/antonkrutov/.codex/instructions/game-localization-audit-workflow.md` to
all 30 VN Revival locales of *The Murder of Sonic the Hedgehog*. It defines
only the pinned inputs, project-specific dependency rules, mandatory regression
surfaces, and validation evidence. It is not an exception to the universal
acceptance algorithm and must not weaken runtime, visual, font, texture,
packaging, or release gates.

## Required inputs

- Pinned Steam build `20535215`, game version `1.01`.
- Canonical English inventory and source fingerprint.
- Exact target locale and the approved 117-entry locale glossary layer.
- The locale manual overlay, compiled overlay, 10 text-bearing image plans,
  and the previous accepted hashes or a clearly recorded absence of them.
- Stable unit IDs and protected runtime syntax. PNG files are outside this
  text-audit workflow and must not be edited here.

## One-time glossary amendment

The owner-authorized exception
`SONIC-CHARACTER-GLOSSARY-MIGRATION-2026-09` is defined in
[`GLOSSARY_AMENDMENT_EXCEPTION.md`](GLOSSARY_AMENDMENT_EXCEPTION.md). Only that
one character-metadata migration may preserve completed semantic coverage
across a changed glossary fingerprint by using its exhaustive per-locale
impact closures and immutable amendment audits. It does not apply to ordinary
glossary changes and does not weaken any runtime, visual, font, texture,
packaging, installation or release gate.

## Universal acceptance sequence applied here

### 1. Full deterministic preflight

Run the project source, overlay, glossary, and localization tests across the
entire corpus before semantic review. Confirm at minimum:

- exactly 3,547 source units and 3,547 target units;
- all 10 text-bearing image plans are present;
- zero missing IDs, extra IDs, protected-token errors, and layout-schema
  errors;
- source inventory, batches, CSV, and image-review records match their pinned
  fingerprints;
- the overlay can be rebuilt from the manual layer byte-for-byte;
- service IDs, Ink commands, paths, placeholders, markup, comparison literals,
  serialized environment keys, and exact-symbol assets remain unchanged.

Mechanical success establishes structural safety, not editorial quality.

### 2. One complete semantic audit

A qualified language model reads every one of the 3,547 source/target pairs and
all 10 image-text plans once with enough scene context to judge meaning,
naturalness, voice, humor, terminology, and grammar. The audit must record its
coverage and the hashes of the reviewed inputs.

The reviewer writes only actionable findings to a compact structured file or
checkpoint entry. Clean lines are not copied into chat or restated in a report.
Each finding identifies the stable unit ID, objective reason, and proposed
correction. Equivalent valid wording is not changed for preference alone.

The full pass always includes character gender and ambiguity. In particular,
review Amy, Rouge, Blaze, every other known-gender referent, and every
`unknown`, `ambiguous`, or `variable/player-selected` case using the rules in
`AGENTS.md` and the canonical glossary.

### 3. Apply corrections and build an immutable dependency closure

Apply accepted corrections only to authored text or allowlisted layout
overrides, then rebuild the derived overlay. Build a review set containing:

- every changed stable ID;
- all repeated uses of the same source or localized wording;
- glossary-linked occurrences and character references affected by the edit;
- the containing exchange or enough neighboring scene context to prove the
  correction;
- any UI surface sharing the same runtime binding or layout constraint.

Do not add every occurrence of every known character merely because one
character-related line changed. The complete semantic pass already covers
unchanged units. Add only the actual referent, grammatical risk, glossary
concept, scene context, repetition, or binding invalidated by the edit, plus
the mandatory regression surfaces below.

Every review cycle writes new immutable evidence instead of overwriting the
previous cycle:

- reviewed manual, overlay, image-plan, source, inventory, and glossary hashes;
- `changed-ids`, `closure-ids`, and review rows in canonical source order;
- separate component lists for context, repetitions, glossary/referents,
  runtime bindings, and mandatory regression surfaces;
- counts and SHA-256 for every list, with an explicit newline convention.

Do not restart a full model reread merely because isolated corrections were
made. Unchanged units retain the evidence of the complete semantic audit.

### 4. Clean dependency-aware diff audit

An independent reviewer checks the complete dependency closure against the
source, glossary, and scene context. The first diff cycle checks every changed
ID, the complete first closure, and the mandatory regression set.

After corrections, do not reread the whole closure automatically. The next
review set is exactly the union of:

- IDs corrected since the last reviewed freeze;
- dependency IDs newly added in `closure-N - closure-(N-1)`;
- previously reviewed IDs whose source, glossary evidence, referent, context,
  runtime binding, or shared wording was explicitly invalidated.

Record removed dependency IDs, but do not reread unchanged removed rows. Keep
every old closure list immutable so the delta is reproducible. If the previous
list was lost or its hash cannot be verified, reconstruct it exactly or reread
the full current closure; never guess the delta. Repeat the delta review until
it is clean on one unchanged set of artifact and closure hashes.

The following regression suite is mandatory even when none of its strings
appears in the ordinary diff:

- Amy, Rouge, and Blaze gendered self-reference and references to them;
- all target-language gender, feminine-form, pronoun, honorific, role-noun,
  title, profession, kinship, and agreement risks required by `AGENTS.md`;
- runner HUD `RingsLabel`, including wrapping and its locale layout override;
- save/load headings, slot location, timestamp, and collision constraints;
- all 13 environment keys and all 11 unique save-location display values,
  including exact internal `Conductor  Car` and `Final  Push` forms;
- all six establishing-shot titles and all 17 speaker display labels;
- all 10 image-text plans, while preserving required symbols and numbers.

The reviewer reports only findings and the exact covered IDs/surfaces. A clean
diff audit is valid only when the audited artifact and closure hashes do not
change afterward.

### 5. Full final machine gate

Run the full deterministic preflight again on the final hashes. The locale is
editorially accepted only when all of the following are recorded together:

- complete semantic coverage: 3,547/3,547 and 10/10;
- clean diff audit of every changed unit and its dependency closure;
- clean mandatory regression suite;
- byte-identical rebuilt overlay;
- zero missing, extra, protected-token, and layout errors;
- final manual, overlay, and image-plan SHA-256 values;
- unresolved source placeholders or runtime questions explicitly classified,
  never hidden by the validator.

Runtime and visual checks remain separate statuses. Static acceptance must not
be reported as proof that text renders correctly in the game.

## When a new full semantic audit is mandatory

Discard prior semantic coverage and repeat step 2 over the full corpus when:

- the English source, source fingerprint, or canonical inventory changes;
- the applicable glossary content or character-gender evidence changes;
- runtime extraction/reinsertion changes which text is visible or how it is
  bound;
- an ID migration, batch realignment, or parser defect may have shifted text;
- a systemic error cannot be exhaustively bounded by stable IDs and added to
  the dependency closure;
- hashes or coverage evidence are missing, inconsistent, or unverifiable.

An isolated wording or allowlisted layout correction does not trigger a full
restart when its dependency closure is complete and independently audited.
An exhaustively searchable systemic wording issue also remains a diff audit
when every occurrence is enumerated, added to the closure, and reviewed in
context; otherwise restart the full semantic audit.

## Token and agent discipline

- Give each reviewer only file paths, stable instructions, the target locale,
  the relevant glossary, and the compact checkpoint. Do not fork the full chat
  history into a new audit task.
- Use a high-reasoning language reviewer for the complete semantic pass and
  disputed contextual findings. Use scripts for deterministic checks and a
  lower-cost review mode for routine classification or report formatting.
- Keep reusable instructions stable and append locale-specific data after
  them. Do not paste clean source/target pairs back into the response.
- Preserve every closure snapshot. Never overwrite the only copy of an earlier
  ID list or TSV; later cycles depend on an exact set difference.
- Parallel review reduces elapsed time, not total token use. Start parallel
  agents only for genuinely independent locales or review sets.
- Record measured input, cached-input, output, and reasoning usage by locale
  and phase when available. Do not estimate it from file size.

## Checkpoint record

For each locale, store the pinned source/glossary fingerprints, reviewed
artifact hashes, 3,547/3,547 and 10/10 coverage, finding count, changed-ID and
per-cycle dependency-closure counts and hashes, exact delta-review sets,
regression-suite result, validator results, remaining `needs-review` items,
runtime/visual status, model and reasoning level, and measured usage when
available.

Historical audits remain valid evidence of what was actually performed. Do not
rewrite them to pretend they followed this workflow retroactively.
