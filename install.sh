#!/usr/bin/env bash
# XS-UI public installer; Ubuntu/Debian x86_64, fixed release and SHA-256.
set -euo pipefail
umask 077
if [[ ${EUID} -ne 0 ]]; then
  command -v sudo >/dev/null || { echo '请以 root 运行安装命令。' >&2; exit 1; }
  copy=$(mktemp)
  trap 'rm -f -- "$copy"' EXIT
  cat -- "$0" > "$copy"
  sudo bash "$copy"
  exit $?
fi
[[ -r /etc/os-release ]] || { echo '无法识别系统。'; exit 1; }
. /etc/os-release
case "${ID:-}:$(uname -m)" in
  ubuntu:x86_64|debian:x86_64) ;;
  *) echo '此安装包支持 Ubuntu/Debian x86_64。请在 VPS 控制台选择 Ubuntu 24.04 或 Debian 12/13 的 x86_64 系统。'; exit 1;;
esac
[[ -d /run/systemd/system ]] || { echo '此安装器需要 systemd。'; exit 1; }
[[ ! -e /opt/xs-ui && ! -e /var/lib/xs-ui ]] || { echo '已有 XS-UI 安装，已停止以保护数据。'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl python3 iproute2 procps passwd coreutils util-linux tar gzip openssl
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
asset='XS-UI-linux-amd64.tar.gz'
url='https://github.com/Bapai6268/XS-UI/releases/download/v0.1.0-dev.3/'"$asset"
if ! curl --proto '=https' --tlsv1.2 --fail --location --retry 3 --connect-timeout 15 --max-time 900 "$url" -o "$work_dir/$asset"; then
  echo '下载安装包失败。请确认仓库已设为 Public，且 v0.1.0-dev.3 已发布；无需 GitHub 登录。' >&2
  exit 1
fi
printf '%s  %s\n' 'd5fa50ca264bac77e477b96f3a96a06f4f056ab4a3fdcc20a1ae2e74f0a1517e' "$asset" > "$work_dir/SHA256SUMS"
python3 - "$work_dir" <<'XS_UI_VERIFY_ARCHIVE'
#!/usr/bin/env python3
"""Validate a private release and extract only its expected flat regular files."""
import hashlib
from pathlib import Path,PurePosixPath
import re
import sys
import tarfile

EXPECTED={'sui','sui.sha256','install-local.sh','xs-ui.service','configure_bbr.py','verify_install.py','set_panel_listener.py','show_access.py','prepare_firewall.sh','LICENSE','NOTICE','BUILD_TAGS'}

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

XS_UI_VERIFY_ARCHIVE
# dev.3 readiness hotfix: retain the verified immutable binary/archive, but use
# this installer revision's checked-in readiness checker. No extra network fetch.
cat > "$work_dir/package/verify_install.py" <<'XS_UI_READINESS_HOTFIX'
#!/usr/bin/env python3
"""Check API/core/listeners; unrelated log levels never determine readiness."""
import http.cookiejar
import json
import sys
import subprocess
import time
import urllib.parse
import urllib.request

def verify_listeners(ports, execute=subprocess.check_output, public_panel=False):
    lines=execute(['ss','-H','-ltn'],text=True).splitlines()
    seen=set()
    for line in lines:
        fields=line.split()
        if len(fields)<4:continue
        address, separator, port=fields[3].rpartition(':')
        if not separator or not port.isdigit() or int(port) not in ports:continue
        allowed=('0.0.0.0','[::]','::','*') if public_panel and int(port)==ports[0] else ('127.0.0.1','[::1]','::1')
        if address not in allowed:
            raise RuntimeError(f'Unexpected listener binding on port {port}: {address}')
        seen.add(int(port))
    if seen!=set(ports):raise RuntimeError('Listeners are not ready; missing ports: '+','.join(map(str,sorted(set(ports)-seen))))

def verify(path,public_panel=False):
    with open(path) as stream:
        account=json.load(stream)
    port=account['port']
    sub_port=account['sub_port']
    if any(type(value) is not int or not 1024 <= value <= 65535 for value in (port,sub_port)) or port==sub_port:
        raise RuntimeError('Invalid local panel port')
    origin=f'http://127.0.0.1:{port}'
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(action,data=None):
        body=None if data is None else urllib.parse.urlencode(data).encode()
        req=urllib.request.Request(origin+'/app/api/'+action,data=body,headers={'Origin':origin,'X-Requested-With':'XMLHttpRequest'})
        with client.open(req,timeout=3) as response:return json.load(response)
    # Do not scan journal ERROR lines: the optional Naive outbound build warning
    # is unrelated to whether the panel and sing-box are operational.
    last_reason='No successful readiness response'
    for attempt in range(30):
        try:
            login=request('login',{'user':account['username'],'pass':account['password']})
            if not login.get('success'):raise RuntimeError('Login verification failed')
            result=request('status?r=sbd')
            if result.get('obj',{}).get('sbd',{}).get('running') is not True:
                raise RuntimeError('Proxy core API does not report running=true')
            verify_listeners((port,sub_port),public_panel=public_panel)
            # Logout cleanup must not turn a healthy service into installation failure.
            try:request('logout')
            except Exception:pass
            print('PASS: panel login, expected listener bindings and proxy core readiness. Public nodes/certificates still require tests.')
            return
        except RuntimeError as error:
            last_reason=str(error)
        except Exception as error:
            # Do not echo HTTP bodies, submitted credentials or raw exception text.
            last_reason='Readiness request/check failed: '+type(error).__name__
        if attempt<29:time.sleep(1)
    raise RuntimeError('Readiness failed: '+last_reason+'. Inspect sudo journalctl -u xs-ui; initial credentials saved in /root/xs-ui-access.json (root only).')

if __name__=='__main__':
    try:verify(sys.argv[1],public_panel='--public-panel' in sys.argv[2:])
    except Exception as error:raise SystemExit(str(error))
XS_UI_READINESS_HOTFIX
bash "$work_dir/package/install-local.sh"
