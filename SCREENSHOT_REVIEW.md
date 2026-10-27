# Screenshot review

New review work uses the shared queue maintained in the canonical SiteForMods checkout.
Existing capture and review processes are not modified or redirected.

Entry point: `python3 Scripts/visual-qa/review_screenshots.py`. Read the complete protocol at
`../SiteForMods/tools/codex-skills/screenshot-common/references/QUEUE.md`.

Run `python3 Scripts/visual-qa/review_screenshots.py --help` for options. Initialization requires a complete
native manifest or hosted export, a compact acceptance context, explicit
`--model gpt-6.1-sol --reasoning high`, and paths inside this project.
Use a new queue directory outside upload images. All inspection commands
remain text-only; `run` submits nothing without `--execute`.

Only already authorized review may use `run --execute` (one packet) or
`run --execute --all` (sequential fresh processes). Existing matching ledger
judgments are retained after the prior owner has completed and released it.
Each new attempt is immutable, externally timed and never automatically retried.
A held queue requires status inspection and explicit reconciliation; never
delete an active lock or recapture valid originals because a model disconnected.

This entry point changes no translation, runtime, full-resolution visual,
RTL, publication or server permission requirements.
