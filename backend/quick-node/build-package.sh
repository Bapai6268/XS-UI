#!/usr/bin/env bash
# Run from a reviewed checkout, outside the small VPS.
set -euo pipefail
root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
frontend_dir=${1:?Pass the reviewed frontend source directory}
output_dir=${2:?Pass a new package output directory}
[[ ! -e "$output_dir" ]] || { echo 'Output directory already exists' >&2; exit 1; }
[[ -f "$frontend_dir/dist/index.html" ]] || { echo 'Build frontend first' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'This recipe targets x86_64' >&2; exit 1; }
mkdir -p "$root_dir/web/html" "$output_dir"
# Embed precisely this frontend build, not stale assets from a previous one.
python3 - "$root_dir/web/html" "$frontend_dir/dist" <<'PY'
import pathlib,shutil,sys
target,source=map(pathlib.Path,sys.argv[1:])
for child in target.iterdir():
    if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
    else: child.unlink()
shutil.copytree(source,target,dirs_exist_ok=True)
PY
cd "$root_dir"
GOMAXPROCS=2 GOMEMLIMIT=700MiB CGO_ENABLED=1 go build -p 1 -trimpath \
  -tags 'with_quic,with_utls,with_acme,netgo,osusergo,sqlite_omit_load_extension' \
  -ldflags '-w -s -linkmode external -extldflags -static' -o "$output_dir/sui" .
sha256sum "$output_dir/sui" | cut -d ' ' -f 1 > "$output_dir/sui.sha256"
cp quick-node/install-local.sh quick-node/xs-ui.service quick-node/configure_bbr.py quick-node/verify_install.py quick-node/set_panel_listener.py quick-node/show_access.py quick-node/prepare_firewall.sh LICENSE "$output_dir/"
printf '%s\n' 'XS-UI development build based on S-UI v1.6.7. See accompanying source and test report.' > "$output_dir/NOTICE"
printf '%s\n' 'with_quic,with_utls,with_acme,netgo,osusergo,sqlite_omit_load_extension' > "$output_dir/BUILD_TAGS"
