#!/usr/bin/env python3
"""Project entry point for the shared fresh-context screenshot queue."""
import importlib.util
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT.parent / 'SiteForMods/tools/codex-skills/screenshot-common/scripts/review_queue.py'
spec = importlib.util.spec_from_file_location('shared_screenshot_queue', SCRIPT)
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)

if __name__ == '__main__':
    queue.main(project_root=PROJECT)
