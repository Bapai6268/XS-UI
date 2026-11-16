#!/usr/bin/env bash
# Reviewed local-package installer. No downloaded shell code is executed.
# The package's provenance must be verified separately before running as root.
set -euo pipefail
umask 077
die() { printf '%s\n' "$*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || die 'Run with sudo on the designated empty test VPS.'
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die 'This development package supports Linux x86_64 only.'
[[ -r /etc/os-release ]] || die 'Cannot identify Linux distribution.'
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) die "This development installer currently supports Ubuntu/Debian with systemd. Detected: ${ID:-unknown}" ;;
esac
[[ -d /run/systemd/system ]] || die 'systemd is required.'
for command_name in python3 sha256sum runuser useradd systemctl install ss sysctl getent awk grep; do
  command -v "$command_name" >/dev/null || die "Missing prerequisite: $command_name"
done
package_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ -f "$package_dir/sui" && ! -L "$package_dir/sui" ]] || die 'Missing package binary.'
[[ -f "$package_dir/sui.sha256" && -f "$package_dir/xs-ui.service" ]] || die 'Incomplete package.'
expected_hash=$(cat -- "$package_dir/sui.sha256")
[[ $expected_hash =~ ^[a-f0-9]{64}$ ]] || die 'Invalid checksum file.'
actual_hash=$(sha256sum -- "$package_dir/sui")
[[ ${actual_hash%% *} == "$expected_hash" ]] || die 'Binary checksum mismatch.'
for reserved_path in /opt/xs-ui /var/lib/xs-ui /etc/systemd/system/xs-ui.service /root/xs-ui-access.json /var/lib/xs-ui-install /etc/sysctl.d/90-xs-ui-bbr.conf; do
  [[ ! -e "$reserved_path" && ! -L "$reserved_path" ]] || die "Refusing to overwrite: $reserved_path"
done
if getent passwd xs-ui >/dev/null || getent group xs-ui >/dev/null; then
  die 'Reserved service account already exists; inspect prior installation first.'
fi
if ss -H -ltn | awk '{print $4}' | grep -Eq ':(2095|2096)$'; then
  die 'Panel ports 2095 or 2096 are occupied.'
fi
[[ -f "$package_dir/configure_bbr.py" && -f "$package_dir/verify_install.py" ]] || die 'Missing setup helpers.'
setup_file=$(mktemp /run/xs-ui-setup.XXXXXXXX)
trap 'rm -f -- "$setup_file"' EXIT
python3 - "$setup_file" <<'PY'
import json,secrets,sys
with open(sys.argv[1], 'w') as f:
    json.dump({'username':'admin-'+secrets.token_hex(4), 'password':secrets.token_hex(24), 'port':2095, 'sub_port':2096}, f)
PY
useradd --system --user-group --home-dir /var/lib/xs-ui --no-create-home --shell /usr/sbin/nologin xs-ui
install -d -o root -g root -m 0755 /opt/xs-ui
install -d -o xs-ui -g xs-ui -m 0700 /var/lib/xs-ui
install -o root -g root -m 0755 "$package_dir/sui" /opt/xs-ui/sui
runuser -u xs-ui -- env SUI_DB_FOLDER=/var/lib/xs-ui/db /opt/xs-ui/sui quick-init < "$setup_file"
install -o root -g root -m 0600 "$setup_file" /root/xs-ui-access.json
install -o root -g root -m 0644 "$package_dir/xs-ui.service" /etc/systemd/system/xs-ui.service
python3 "$package_dir/configure_bbr.py"
systemctl daemon-reload
systemctl enable --now xs-ui.service
systemctl is-active --quiet xs-ui.service || die 'Startup failed; inspect journalctl -u xs-ui.'
python3 "$package_dir/verify_install.py" /root/xs-ui-access.json
printf '%s\n' \
  'Installed. Management and subscription listeners bind to 127.0.0.1.' \
  'Credentials: /root/xs-ui-access.json (root only).' \
  'Use an SSH tunnel to local port 2095, then open http://127.0.0.1:2095/app/.' \
  'Allow TCP 80 for ACME and your selected proxy ports in the cloud firewall.' \
  'No firewall rules or existing services were changed. Live protocol tests are still required.'
