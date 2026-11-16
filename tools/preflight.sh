#!/usr/bin/env bash
# Read-only report: no changes, passwords, keys, environment dumps or IP enumeration.
set -uo pipefail
printf '=== XS-UI read-only preflight ===\n'
if [[ -r /etc/os-release ]]; then . /etc/os-release; printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"; fi
printf 'Architecture: %s\nKernel: %s\n' "$(uname -m)" "$(uname -r)"
printf 'systemd: '; if [[ -d /run/systemd/system ]]; then echo yes; else echo no; fi
printf 'sudo without prompt: '; if sudo -n true 2>/dev/null; then echo yes; else echo no; fi
printf 'Memory MB: '; awk '/MemTotal:/{printf "%.0f\n",$2/1024}' /proc/meminfo
df -h / /var | awk '!seen[$0]++'
for name in python3 sha256sum runuser useradd systemctl install ss sysctl getent awk grep; do
  command -v "$name" >/dev/null 2>&1 || printf 'Missing prerequisite: %s\n' "$name"
done
for parameter in net.ipv4.tcp_available_congestion_control net.ipv4.tcp_congestion_control net.core.default_qdisc; do
  sysctl "$parameter" 2>/dev/null || true
done
printf 'Existing XS-UI paths: '
found=0
for path in /opt/xs-ui /var/lib/xs-ui /etc/systemd/system/xs-ui.service /root/xs-ui-access.json /var/lib/xs-ui-install /etc/sysctl.d/90-xs-ui-bbr.conf; do
  if [[ -e "$path" || -L "$path" ]]; then printf '%s ' "$path"; found=1; fi
done
[[ $found == 1 ]] || printf 'none visible'
printf '\nRelevant listening ports (no process details):\n'
ss -H -lntu 2>/dev/null | awk '$5 ~ /:(22|80|443|2095|2096)$/ {print $1,$5}' || true
printf '=== End; cloud firewall and DNS still require separate checks ===\n'
