#!/usr/bin/env python3
"""Restore pinned binary build inputs; never replace existing or mismatching data."""
import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

def relative(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value or str(p) != value:
        raise ValueError('Unsafe relative input path')
    return Path(*p.parts)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def verify(target, files):
    if target.is_symlink() or not target.is_dir():
        raise ValueError('Input destination is not a regular directory')
    actual = {}
    for p in target.rglob('*'):
        if p.is_symlink():
            raise ValueError('Symbolic link in restored input')
        if p.is_file():
            actual[p.relative_to(target).as_posix()] = sha(p)
    if actual != files:
        raise ValueError('Input inventory/hash mismatch; existing data preserved')
    return len(actual)

def restore(root, pin, cache):
    target = root / relative(pin['destination'])
    target.parent.resolve().relative_to(ROOT)
    if os.path.lexists(target):
        return {'id': pin['id'], 'status': 'already-present', 'files': verify(target, pin['files'])}
    work_cache = cache / pin['archiveSha256'][:16]
    work_cache.mkdir(parents=True, exist_ok=True)
    archive = work_cache / relative(pin['asset'])
    assert archive.parent == work_cache
    if not archive.exists():
        auth = subprocess.run(['gh', 'auth', 'status', '--hostname', 'github.com'], capture_output=True)
        if auth.returncode:
            raise RuntimeError('GitHub authentication required')
        account = subprocess.check_output(['gh', 'api', 'user', '--jq', '.login'], text=True).strip()
        if account != 'Master1C8':
            raise RuntimeError('Use the canonical GitHub account Master1C8')
        subprocess.run(['gh', 'release', 'download', pin['releaseTag'], '--repo', pin['repository'],
                        '--pattern', pin['asset'], '--dir', str(work_cache)], check=True)
    if sha(archive) != pin['archiveSha256']:
        raise ValueError('Archive checksum mismatch; no input published')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.archival-input-', dir=target.parent) as temporary:
        staged = Path(temporary) / 'input'
        staged.mkdir()
        with zipfile.ZipFile(archive) as z:
            seen = set()
            for member in z.infolist():
                if not member.filename.startswith(pin['archivePrefix']) or member.is_dir():
                    continue
                name = member.filename[len(pin['archivePrefix']):]
                rel = relative(name)
                if name in seen or name not in pin['files'] or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError('Duplicate, unpinned or symlink archive member')
                seen.add(name)
                p = staged / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('xb') as stream:
                    stream.write(z.read(member))
            count = verify(staged, pin['files'])
        if os.path.lexists(target):
            raise ValueError('Destination appeared during restore; preserve for reconciliation')
        staged.rename(target)
    return {'id': pin['id'], 'status': 'restored', 'files': count, 'archiveSha256': pin['archiveSha256']}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, default=ROOT / 'archival-inputs.json')
    ap.add_argument('--input', default='all')
    ap.add_argument('--rehearse', help='Restore under this new project-relative generated directory')
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    root = ROOT / relative(args.rehearse) if args.rehearse else ROOT
    selected = [p for p in manifest['inputs'] if args.input in ['all', p['id']]]
    if not selected:
        raise ValueError('Unknown input identity')
    for pin in selected:
        # Each destination commits independently. A failed later input leaves
        # earlier verified inputs available; reruns validate and continue.
        print(json.dumps(restore(root, pin, ROOT / '.build/archival-recovery'), ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
