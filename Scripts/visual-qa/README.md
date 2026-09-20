# Main-menu visual QA

This runner adapts the checked-in Stardew Valley Oculix workflow to capture the
same localized main menu for every Sonic locale. It uses the package's guarded
installer core as the locale adapter, verifies the receipt, launches through
Steam, waits for the main-menu image marker, captures a native unannotated PNG,
stops the game, restores the prior locale, and confirms that `SaveData.data`
did not change.

```sh
python3 Scripts/visual-qa/run_visual_qa.py --list
python3 Scripts/visual-qa/run_visual_qa.py ru
python3 Scripts/visual-qa/run_visual_qa.py --all
```

An all-locale run resumes missing captures and preserves every existing capture
that already has evidence, including a visual-review failure. Use `--replace`
only after fixing the reported issue and reviewing the existing output.
Upload-ready files are flat under `Screenshots/upload/`; evidence and failure
frames are under `Screenshots/evidence/`.
