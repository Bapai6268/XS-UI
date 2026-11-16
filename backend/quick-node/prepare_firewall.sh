#!/usr/bin/env bash
# Add only necessary defaults to an already active supported host firewall.
# Never enable a firewall or flush existing rules.
set -euo pipefail
if command -v ufw >/dev/null && LC_ALL=C ufw status | grep -q '^Status: active'; then
  for rule in 2095/tcp 80/tcp 443/udp 443/tcp; do ufw allow "$rule"; done
  echo '已为活动的 UFW 放行默认端口；原规则保留。'
elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
  zone=$(firewall-cmd --get-default-zone)
  for rule in 2095/tcp 80/tcp 443/udp 443/tcp; do
    firewall-cmd --zone="$zone" --add-port="$rule"
    firewall-cmd --permanent --zone="$zone" --add-port="$rule"
  done
  echo '已为活动的 firewalld 默认区域放行端口；原规则保留。'
else
  echo '未检测到活动的 UFW/firewalld；若另有主机防火墙，请按最终端口清单放行。'
fi
