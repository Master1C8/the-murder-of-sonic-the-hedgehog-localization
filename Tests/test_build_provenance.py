import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("build_provenance", Path(__file__).parents[1] / "Scripts/build-provenance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProvenanceTests(unittest.TestCase):
    def test_roundtrip_rejects_modified_or_missing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "App"
            stage.mkdir()
            (stage / "file").write_bytes(b"original")
            manifest = root / "vnrevival-release.json"
            manifest.write_text('{"sourceCommit":"pinned"}')
            archive = root / "release.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.write(stage / "file", "App/file")
                z.write(manifest, manifest.name)
            self.assertEqual(module.verify(archive, stage, manifest), 2)
            (stage / "file").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "Archive bytes differ"):
                module.verify(archive, stage, manifest)
            (stage / "file").write_bytes(b"original")
            (stage / "missing").write_bytes(b"not archived")
            with self.assertRaisesRegex(ValueError, "Unexpected or duplicate"):
                module.verify(archive, stage, manifest)

    def test_inventory_rejects_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "file").write_bytes(b"original")
            self.assertEqual(len(module.inventory(root)), 1)
            (root / "link").symlink_to(root / "file")
            with self.assertRaisesRegex(ValueError, "Symlink material"):
                module.inventory(root)
