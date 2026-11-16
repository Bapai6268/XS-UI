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
bash "$work_dir/package/install-local.sh"
