# Historical compatibility evidence

This record explains why the character-metadata migration has not rewritten
any accepted game-text artifact. It is compatibility evidence only: it does
not replace the cycle-1 primary or independent amendment reviews required by
`GLOSSARY_AMENDMENT_EXCEPTION.md`.

The migration formalizes the same owner-confirmed Barry decision and the same
known-character agreement rules used by the accepted audits. The current
`manual`, compiled `overlay`, and `images.manual` files still match the frozen
pre-migration SHA-256 values for all 15 accepted locales.

| Locale | Frozen evidence compatible with the amendment |
| --- | --- |
| `ar` | `ar.audit.json#/sourcePolicy/ownerConfirmedFacts/0` says Barry is male; `mandatoryRegression/genderAndAgreement` records the complete agreement pass. |
| `cs` | `cs.audit.json#/mandatoryRegression/genderAgreement` records Barry and `NamelessMC` as owner-confirmed male and checks all agreement-bearing forms. |
| `de` | `CHECKPOINT.md#Five-locale-Sol-editorial-audit-group` records complete canonical-gender, pronoun, agreement, title, profession and role-noun coverage. |
| `es` | Same five-locale checkpoint evidence; the accepted Barry glossary prose already uses masculine `empleado`. |
| `es-419` | Same five-locale checkpoint evidence; the game-text audit covered canonical gender and player references even though the glossary description itself is lexically neutral. |
| `fa` | `fa.audit.json#/semanticCoverage/genderAndReferencePass` records the complete Persian pronoun, honorific, title, role, kinship, address and referent pass. |
| `hu` | `hu.audit.json#/semanticCoverage/genderAndReferencePass` explicitly says Barry follows the owner's male decision. |
| `id` | `id.audit.json#/findings/open/0/reason` explicitly says Barry was owner-confirmed male and audited as male; the amendment resolves that recorded metadata debt. |
| `it` | `it.audit.json#/mandatoryRegression/semanticGenderReview` explicitly says Barry is owner-confirmed male; the audit contains concrete Barry-agreement corrections and an independent closure audit. |
| `ja` | The five-locale checkpoint records complete canonical-gender and reference coverage; Japanese wording did not require a new inflection in the unchanged Barry glossary prose. |
| `nl` | `nl.audit.json#/semanticCoverage/genderAndReferencePass` records all ambiguous/player references; the accepted Barry glossary prose already uses masculine possessive `zijn`. |
| `pt-BR` | The five-locale checkpoint records complete canonical-gender and agreement coverage; the accepted Barry glossary prose already uses masculine `novo funcionário`. |
| `th` | `th.audit.json#/semanticCoverage/genderAndReferencePass` explicitly records owner-confirmed male Barry and the Thai particle/address review. |
| `uk` | `uk.audit.json#/sourcePolicy/ownerConfirmedFacts/0` says Barry is male; `mandatoryRegression/genderAndAgreement` records the complete agreement pass. |
| `vi` | `vi.audit.json#/sourcePolicy/ownerConfirmedFacts/0` says Barry is male; the audit records Barry-specific pronoun and male-address corrections. |

The five-locale checkpoint evidence covers `de`, `es`, `es-419`, `ja`, and
`pt-BR`. The remaining ten locales have dedicated audit JSON. This accounts
for all 15 accepted locales; it does not collapse Spanish and Latin American
Spanish into one locale.
