#!/usr/bin/env python3
"""Repair the user's existing dev.2 loopback setup; run as root on that VPS."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

def main():
    if os.geteuid()!=0:raise RuntimeError('Run with sudo')
    path=Path('/var/lib/xs-ui/db/s-ui.db')
    if not path.is_file() or path.is_symlink():raise RuntimeError('Expected existing XS-UI database')
    fd,backup=tempfile.mkstemp(prefix='xs-ui-before-public-',suffix='.db',dir='/root')
    os.close(fd)
    source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)
    target=sqlite3.connect(backup)
    try:source.backup(target)
    finally:target.close();source.close()
    code='''import sqlite3
db=sqlite3.connect("file:/var/lib/xs-ui/db/s-ui.db?mode=rw",uri=True,timeout=10)
try:
    with db:
        rows=db.execute("SELECT value FROM settings WHERE key=?",("webListen",)).fetchall()
        if len(rows)!=1 or rows[0][0] not in ("127.0.0.1","0.0.0.0"):raise RuntimeError("Unexpected panel setting; no change made")
        db.execute("UPDATE settings SET value=? WHERE key=?",("0.0.0.0","webListen"))
finally:db.close()
'''
    subprocess.run(['runuser','-u','xs-ui','--','python3','-c',code],check=True)
    subprocess.run(['systemctl','restart','xs-ui'],check=True)
    subprocess.run(['systemctl','is-active','--quiet','xs-ui'],check=True)
    listeners=subprocess.check_output(['ss','-H','-ltn'],text=True)
    if not any(len(line.split())>3 and line.split()[3]=='0.0.0.0:2095' for line in listeners.splitlines()):
        raise RuntimeError('Public panel listener not ready; inspect sudo journalctl -u xs-ui')
    account=json.loads(Path('/root/xs-ui-access.json').read_text())
    print('访问地址：http://115.159.42.145:2095/app/')
    print('端口：2095')
    print('账号：'+account['username'])
    print('密码：'+account['password'])
    print('配置前备份：'+backup)
    print('HTTP 登录不加密；首次配置后请设置 HTTPS。')

if __name__=='__main__':main()
