#!/usr/bin/env python3
"""Enable kernel TCP BBR without changing the kernel, SSH or firewall."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

KEYS = ('net.core.default_qdisc', 'net.ipv4.tcp_congestion_control')

def run(args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()

def configure(execute=run, config=Path('/etc/sysctl.d/90-xs-ui-bbr.conf'), backup=Path('/var/lib/xs-ui-install/network-before.json')):
    available = execute(['sysctl', '-n', 'net.ipv4.tcp_available_congestion_control']).split()
    if 'bbr' not in available:
        try:
            execute(['modprobe', 'tcp_bbr'])
        except (OSError, subprocess.CalledProcessError):
            return 'SKIPPED: kernel BBR is unavailable; no kernel upgrade or reboot performed.'
        available = execute(['sysctl', '-n', 'net.ipv4.tcp_available_congestion_control']).split()
    if 'bbr' not in available:
        return 'SKIPPED: kernel did not expose BBR; existing TCP settings retained.'
    before = {key: execute(['sysctl', '-n', key]) for key in KEYS}
    if not all(re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value) for value in before.values()):
        raise RuntimeError('Unexpected sysctl values; refusing changes')
    controller = before[KEYS[1]] if before[KEYS[1]].startswith('bbr') else 'bbr'
    content = '# Managed by XS-UI; previous values are in /var/lib/xs-ui-install/network-before.json\n' + f'{KEYS[0]} = fq\n{KEYS[1]} = {controller}\n'
    if config.is_symlink() or backup.is_symlink():
        raise RuntimeError('Refusing symlink configuration or backup')
    if config.exists() and config.read_text() != content:
        raise RuntimeError('Existing BBR file differs; manual inspection required')
    backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(before, stream)
    temporary = None
    try:
        for key, value in zip(KEYS, ('fq', controller)):
            execute(['sysctl', '-w', f'{key}={value}'])
        for key, value in zip(KEYS, ('fq', controller)):
            if execute(['sysctl', '-n', key]) != value:
                raise RuntimeError('Kernel did not retain requested setting')
        config.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.xs-ui-', dir=config.parent)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, config)
        temporary = None
    except Exception as error:
        failures = []
        for key, value in before.items():
            try:
                execute(['sysctl', '-w', f'{key}={value}'])
            except Exception:
                failures.append(key)
        if failures:
            raise RuntimeError('BBR failed; manual restoration required for: '+', '.join(failures)) from error
        raise RuntimeError('BBR setup failed; original runtime values restored') from error
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return 'ENABLED: kernel TCP '+controller+' with fq; original settings recorded.'

if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run as root only on the intended VPS')
    print(configure())
