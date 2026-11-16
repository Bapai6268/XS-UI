import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('listener',Path(__file__).with_name('set_panel_listener.py'))
listener=importlib.util.module_from_spec(spec);spec.loader.exec_module(listener)

class ListenerSettingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'db.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE settings (key TEXT,value TEXT)')
            db.executemany('INSERT INTO settings VALUES (?,?)',[('webListen','127.0.0.1'),('subListen','127.0.0.1'),('webPort','2095'),('webCertFile',''),('config','keep')])
    def test_only_panel_listener_changes_and_repeat_is_safe(self):
        listener.configure(self.path);listener.configure(self.path)
        with sqlite3.connect(self.path) as db:values=dict(db.execute('SELECT key,value FROM settings'))
        self.assertEqual(values,dict(webListen='0.0.0.0',subListen='127.0.0.1',webPort='2095',webCertFile='',config='keep'))
    def test_custom_listener_refused(self):
        with sqlite3.connect(self.path) as db:db.execute("UPDATE settings SET value='192.0.2.2' WHERE key='webListen'")
        with self.assertRaises(RuntimeError):listener.configure(self.path)
    def test_missing_file_not_created(self):
        missing=self.path.with_name('missing.db')
        with self.assertRaises(RuntimeError):listener.configure(missing)
        self.assertFalse(missing.exists())
    def test_duplicate_key_refused(self):
        with sqlite3.connect(self.path) as db:db.execute("INSERT INTO settings VALUES ('webListen','127.0.0.1')")
        with self.assertRaises(RuntimeError):listener.configure(self.path)

if __name__=='__main__':unittest.main()
