# Main-menu visual QA

This runner adapts the checked-in Stardew Valley Oculix workflow to capture the
same localized UI screens for every Sonic locale. It uses the package's guarded
installer core as the locale adapter, verifies the receipt, launches through
Steam, waits for image markers before and after transitions, captures native
unannotated PNGs, stops the game, restores the prior locale, and confirms that
`SaveData.data` did not change.

The default `main-menu` scenario produces screenshot `01`. The `load-game`
scenario guards the main menu, clicks Continue in calibrated logical Retina
coordinates, guards the save-slot dialog, and produces screenshot `02` without
opening or writing a save.

The Russian catalog showcase captures all six requested screens in one game
process: main menu, load menu, Shadow's action list, a character dialogue, the
evidence-items menu, and the DreamGear runner screen with the localized Rings
HUD. It follows the owner-provided reference route, starts Shadow's
interrogation, advances the dialogue with buffered double clicks, captures and
selects Hidden Passage, then stops the game and verifies that the save file did
not change. This native path is the recorded fallback for the current Oculix
`Mouse.init` incompatibility.

```sh
python3 Scripts/visual-qa/run_visual_qa.py --list
python3 Scripts/visual-qa/run_visual_qa.py ru
python3 Scripts/visual-qa/run_visual_qa.py ru --screen load-game
python3 Scripts/visual-qa/run_visual_qa.py ru --showcase --replace
python3 Scripts/visual-qa/run_visual_qa.py --all
python3 Scripts/visual-qa/run_visual_qa.py --all --screen load-game
```

An all-locale run resumes missing captures and preserves every existing capture
that already has evidence, including a visual-review failure. Use `--replace`
only after fixing the reported issue and reviewing the existing output.
Upload-ready files are flat under `Screenshots/upload/`; evidence and failure
frames are under `Screenshots/evidence/`.
