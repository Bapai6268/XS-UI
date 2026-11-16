import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('release',Path(__file__).with_name('verify-release.py'))
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def make(self,replace=None,extra=None):
        path=self.root/'XS-UI-linux-amd64.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            for name in sorted(release.EXPECTED):
                item=tarfile.TarInfo(name);item.size=2
                if replace and name=='sui':item=replace
                archive.addfile(item,io.BytesIO(b'ok') if item.isfile() else None)
            if extra:archive.addfile(extra,io.BytesIO(b''))
        (self.root/'SHA256SUMS').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n')
    def test_valid(self):
        self.make();self.assertEqual({p.name for p in release.extract(self.root).iterdir()},release.EXPECTED)
    def test_checksum_mismatch(self):
        self.make();(self.root/'SHA256SUMS').write_text('0'*64+'  XS-UI-linux-amd64.tar.gz\n')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):release.extract(self.root)
    def test_path_traversal(self):
        item=tarfile.TarInfo('../outside');item.size=2;self.make(replace=item)
        with self.assertRaises(ValueError):release.extract(self.root)
        self.assertFalse((self.root/'package').exists())
    def test_symlink_and_hardlink(self):
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):
            item=tarfile.TarInfo('sui');item.type=kind;item.linkname='/etc/shadow';self.make(replace=item)
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'Unsafe'):release.extract(self.root)
    def test_duplicate_entry(self):
        self.make(extra=tarfile.TarInfo('sui'))
        with self.assertRaisesRegex(ValueError,'entries'):release.extract(self.root)
    def test_unknown_entry(self):
        self.make(extra=tarfile.TarInfo('unexpected.sh'))
        with self.assertRaisesRegex(ValueError,'entries'):release.extract(self.root)

if __name__=='__main__':unittest.main()
