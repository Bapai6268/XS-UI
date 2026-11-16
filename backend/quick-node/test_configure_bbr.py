import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('bbr', Path(__file__).with_name('configure_bbr.py'))
bbr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bbr)

class BBRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.values = dict(zip(bbr.KEYS, ('fq_codel', 'cubic')))
        self.available = 'reno cubic bbr'
        self.calls = []
        self.fail_bbr = False
    def execute(self, args):
        self.calls.append(args)
        if args[0] == 'modprobe': raise subprocess.CalledProcessError(1, args)
        if args[1] == '-n':
            return self.available if args[2].endswith('available_congestion_control') else self.values[args[2]]
        key, value = args[2].split('=', 1)
        if self.fail_bbr and value == 'bbr': raise subprocess.CalledProcessError(1,args)
        self.values[key] = value
        return ''
    def configure(self):
        return bbr.configure(self.execute,self.root/'sysctl.conf',self.root/'state/before.json')
    def test_success_and_repeat_preserve_original_backup(self):
        self.assertTrue(self.configure().startswith('ENABLED'))
        original=(self.root/'state/before.json').read_text()
        self.configure()
        self.assertEqual(original,(self.root/'state/before.json').read_text())
        self.assertIn('cubic',original)
        self.assertEqual(self.values[bbr.KEYS[1]],'bbr')
    def test_unsupported_does_not_mutate_sysctl(self):
        self.available='reno cubic'
        self.assertTrue(self.configure().startswith('SKIPPED'))
        self.assertFalse(any('-w' in x for x in self.calls))
    def test_partial_failure_restores_both_values(self):
        self.fail_bbr=True
        with self.assertRaisesRegex(RuntimeError,'restored'): self.configure()
        self.assertEqual(self.values,dict(zip(bbr.KEYS,('fq_codel','cubic'))))
        self.assertFalse((self.root/'sysctl.conf').exists())
    def test_existing_foreign_file_is_not_overwritten(self):
        (self.root/'sysctl.conf').write_text('operator-owned')
        with self.assertRaisesRegex(RuntimeError,'differs'): self.configure()
        self.assertFalse(any('-w' in x for x in self.calls))

if __name__=='__main__': unittest.main()
