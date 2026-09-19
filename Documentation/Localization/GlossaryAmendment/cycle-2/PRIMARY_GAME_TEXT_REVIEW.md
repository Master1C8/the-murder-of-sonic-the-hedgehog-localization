# Cycle 2 primary game-text amendment review

Date: 2026-09-19  
Result: complete first semantic pass; corrections required.

Five qualified reviewers read every one of the 3,547 source/target rows and all
10 text-bearing image plans for each of the 15 accepted locales. No sampling or
search-only result is credited.

| Locale | Text coverage | Image coverage | Corrected text IDs | Corrected image plans |
| --- | ---: | ---: | ---: | ---: |
| `ar` | 3,547/3,547 | 10/10 | 2 | 0 |
| `cs` | 3,547/3,547 | 10/10 | 1 | 0 |
| `de` | 3,547/3,547 | 10/10 | 17 | 0 |
| `es` | 3,547/3,547 | 10/10 | 5 | 0 |
| `es-419` | 3,547/3,547 | 10/10 | 33 | 2 |
| `fa` | 3,547/3,547 | 10/10 | 6 | 2 |
| `hu` | 3,547/3,547 | 10/10 | 26 | 0 |
| `id` | 3,547/3,547 | 10/10 | 22 | 1 |
| `it` | 3,547/3,547 | 10/10 | 15 | 1 |
| `ja` | 3,547/3,547 | 10/10 | 11 | 0 |
| `nl` | 3,547/3,547 | 10/10 | 13 | 0 |
| `pt-BR` | 3,547/3,547 | 10/10 | 17 | 0 |
| `th` | 3,547/3,547 | 10/10 | 28 | 7 |
| `uk` | 3,547/3,547 | 10/10 | 19 | 0 |
| `vi` | 3,547/3,547 | 10/10 | 2 | 0 |

The findings covered meaning reversals, broken runtime-composed fragments,
untranslated visible speaker prefixes and checkpoint values, canonical term
drift, translated protected scoreboard literals, person/number agreement,
voice consistency, image logo lockups, and explicit masculine agreement for
Barry. Train's owner-confirmed `male` personified references were checked while
preserving the character's non-human canonical identity and target-language
lexical noun agreement.

All accepted corrections were applied only to authored locale manuals and
image plans. Exact per-locale IDs and image paths, in canonical order, are
frozen under `../cycle-3/changed-ids.<locale>.txt` and
`../cycle-3/changed-image-plans.<locale>.txt`. Their counts and hashes, plus
the corrected manual, overlay, and image-plan hashes, are in
`../cycle-3/artifact-hashes.json`.

The primary pass found 173 unique changed text IDs across locales. Each
corrected overlay was rebuilt from its manual; structural validation reports
3,547/3,547, zero missing/extra IDs, zero protected-token errors, and zero
layout errors. The inherited 11 source-side placeholder records remain
classified `needsReview` and were not changed.
