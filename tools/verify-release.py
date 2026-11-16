#!/usr/bin/env python3
"""Validate a private release and extract only its expected flat regular files."""
import hashlib
from pathlib import Path,PurePosixPath
import re
import sys
import tarfile

EXPECTED={'sui','sui.sha256','install-local.sh','xs-ui.service','configure_bbr.py','verify_install.py','LICENSE','NOTICE','BUILD_TAGS'}

def extract(root,name='XS-UI-linux-amd64.tar.gz'):
    root=Path(root)
    matches=[line.split() for line in (root/'SHA256SUMS').read_text().splitlines() if line.split() and line.split()[-1]==name]
    if len(matches)!=1 or len(matches[0])!=2 or not re.fullmatch('[a-f0-9]{64}',matches[0][0]):raise ValueError('Invalid release checksum manifest')
    archive_path=root/name
    if archive_path.stat().st_size>100*1024*1024:raise ValueError('Unexpected compressed size')
    with archive_path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(stream.read()).hexdigest()
    if digest!=matches[0][0]:raise ValueError('Release checksum mismatch')
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if len(members)!=len(EXPECTED) or {m.name for m in members}!=EXPECTED:raise ValueError('Unexpected package entries')
        if any(m.size<0 for m in members) or sum(m.size for m in members)>200*1024*1024:raise ValueError('Unexpected package size')
        for member in members:
            if not member.isfile() or PurePosixPath(member.name).name!=member.name:raise ValueError('Unsafe archive entry')
        dest=root/'package'
        dest.mkdir(mode=0o700)
        for member in members:
            with archive.extractfile(member) as source,(dest/member.name).open('xb') as target:target.write(source.read())
    return dest

if __name__=='__main__':
    try:extract(Path(sys.argv[1]))
    except Exception as error:raise SystemExit(str(error))
