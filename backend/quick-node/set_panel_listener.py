#!/usr/bin/env python3
"""Change only the panel listener in an existing initialized database."""
from pathlib import Path
import sqlite3
import sys

def configure(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise RuntimeError('Expected an existing regular database')
    with sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=10) as db:
        rows=db.execute('SELECT value FROM settings WHERE key=?',('webListen',)).fetchall()
        if len(rows)!=1 or rows[0][0] not in ('127.0.0.1','0.0.0.0'):
            raise RuntimeError('Unexpected panel listener; inspect before changing')
        db.execute('UPDATE settings SET value=? WHERE key=?',('0.0.0.0','webListen'))

if __name__=='__main__':configure(Path(sys.argv[1]).resolve())
