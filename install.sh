#!/usr/bin/env bash
# Private-repository release installer. Run as the logged-in regular user.
set -euo pipefail
repo='Bapai6268/XS-UI'
release='v0.1.0-dev.2'
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'This release currently supplies Linux x86_64 only.' >&2; exit 1; }
command -v gh >/dev/null || { echo 'GitHub CLI is required to download the private release. Authenticate on this machine first.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3 is required.' >&2; exit 1; }
gh auth status --hostname github.com >/dev/null 2>&1 || { echo 'Private repository access is not authorized. No installation performed.' >&2; exit 1; }
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
asset='XS-UI-linux-amd64.tar.gz'
gh release download "$release" --repo "$repo" --pattern "$asset" --pattern 'SHA256SUMS' --dir "$work_dir"
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
python3 "$source_dir/tools/verify-release.py" "$work_dir"
sudo bash "$work_dir/package/install-local.sh"
