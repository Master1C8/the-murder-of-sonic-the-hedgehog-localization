# Cycle 1 primary amendment review

Date: 2026-09-19  
Reviewer: primary Codex reviewer  
Result: clean for the locally amended glossary; independent review remains
required before the exception can be consumed.

## Reviewed immutable inputs

- Old canonical fingerprint:
  `6585d55f77a0e23e98e946376318305d91234e7b7b9e212a45b42331ae08673f`.
- New canonical fingerprint:
  `7c7921e245e6833398acb129797248785298dfbec935370752fff8c742448145`.
- Source-unit SHA-256:
  `7c3cbc60eec5570d4b07c2f3b44da2abec3173158df4a4c181c7014aaa8dd2af`.
- Reviewed source entries: 16/16 changed character entries.
- Reviewed localized metadata: 16/16 changed entries in each of 30/30
  localized layers, 480 controlled suffixes in total.
- Reviewed structure: 117/117 IDs in source and every localized layer; Barry
  first; zero stable-ID, term, non-character-meaning, or pre-existing localized
  prose changes.
- Historical game-text compatibility: 15/15 accepted locales accounted for in
  `HISTORICAL_COMPATIBILITY.md`; their manual, overlay, and image-plan hashes
  remain unchanged. This compatibility check is not credited as a new full
  game-text audit.

## Character evidence and category review

| ID | Category | Evidence reviewed |
| --- | --- | --- |
| `barry` | `male` | Direct owner decision on 2026-09-19. `Barry` and pre-name `NamelessMC` are one stable player identity; no ID or runtime comparison literal changed. |
| `sonic-the-hedgehog` | `male`; `he/him` | `ink:root[2].Saloon[4].FirstVisit[0][36].g-0[14]` refers to Sonic as “He” and “him”. |
| `amy-rose` | `female`; `she/her` | `ink:root[2].Saloon[4].FirstVisit[0][36].g-0[0]` refers to Amy as “she”. |
| `tails` | `male`; `he/him` | `ink:root[2].Library[4].Bookshelf[17]` and `[20]` refer to the immediately acting Tails as “He”. |
| `knuckles` | `male`; `he/him` | `ink:root[2].Saloon[4].FirstVisit[0][36].g-1[35]` refers to the immediately speaking Knuckles as “He”. |
| `rouge` | `female`; `she/her` | `ink:root[2].Saloon[4].Interrogation_Part4_Have_Correct_Clue[0][8].b[66]` refers to Rouge as “She”. |
| `blaze` | `female`; `she/her` | `ink:root[2].Casino[5].Heist_Planning_Pt2[0][26].c-2[6]` and `[8]` refer to Blaze as “Her/her”. |
| `shadow` | `male`; `he/him` | `ink:root[2].Library[4].Vector_Espio_Train_Map_Explanation[75]` refers to the immediately named Shadow as “He”. |
| `vector` | `male`; `he/him` | `ink:root[2].Saloon[4].Interrogation_Part3[28]` says “It’s Vector! He’s…”. |
| `espio` | `male`; `he/him` | `ink:root[2].Library[4].Enter_Interrogation_Mode[57]` says “Once Espio starts reading, he…”. |
| `the-conductor` | `male`; `he/him` | `ink:root[2].Conductor_Car[32]` refers to the missing Conductor as “him”; further Conductor Car rows use `he/his`. |
| `the-train` | translation grammar `male`; canonical gender `none`; `it/its` | The English corpus consistently uses `it/its`, including `ink:root[2].Prologue[1].Conductor_Info_Dump[0][3]` and `[5]`. The translation category controls required agreement without recasting the non-human character as canonically male. |
| `dr-eggman` | `male`; `he/him` | `ink:root[2].Casino[5].Poker_Chips[14]` refers to Dr. Eggman as “He”. |
| `orbot` | translation grammar `male` | Speaking unit `ink:root[2].Final_Push[35].Ending1_For_Non_Completionists[90]`; official SEGA Sonic Channel material refers to Orbot with masculine `彼`: `https://sonic.sega.jp/SonicChannel/special/sidestory/comic/20161021_001192/`. |
| `cubot` | translation grammar `male` | Speaking unit `ink:root[2].Final_Push[35].Ending1_For_Non_Completionists[99]`; official SEGA profile: `https://sonic.sega.jp/SonicChannel/character/cubot.html`, read together with the official Orbot/Cubot character material and established masculine localization treatment. |
| `conductors-wife` | `female`; `she/her` | `ink:root[2].Prologue[1].FirstVisit[0][48].g-0[7]` identifies the Conductor's wife and immediately uses “She”. |

`Arm` and `Flicky` remain outside the semantic speaking-character roster: their
speaker rows contain only ellipses or bird calls. `Everyone` is a group label.

## Source and localized-layer findings

- The 16 category assignments are compatible with the reviewed evidence.
- Barry is correctly first and remains stable ID `barry`.
- Every localized layer carries exactly the same controlled category value as
  its canonical entry. The metadata tokens are intentionally invariant control
  values; they do not replace or rewrite the surrounding localized prose.
- No localized term changed. No pre-existing localized meaning changed after
  removal of the exact controlled suffix. No dependency contradiction was
  found in the accepted-locale historical evidence.
- No game-text correction was required in this primary cycle, so no delta
  closure was created.

## Remaining gate

The independent reviewer must check this exact source and localized changed
set plus the frozen compatibility evidence on unchanged hashes. Until that
happens, cycle 1 remains `awaiting-independent-review` and the one-time
exception remains `in-progress`.
