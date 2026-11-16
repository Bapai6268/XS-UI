#!/usr/bin/env python3
"""Print initial installation credentials and required firewall ports."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import urllib.request

def public_v4(value):
    try:
        address=ipaddress.ip_address(value.strip())
        return str(address) if address.version==4 and address.is_global else None
    except ValueError:return None

def detect_ip():
    override=public_v4(os.environ.get('XS_UI_PUBLIC_IP',''))
    if override:return override
    try:
        interfaces=json.loads(subprocess.check_output(['ip','-j','-4','addr','show','scope','global'],text=True))
        for interface in interfaces:
            for address in interface.get('addr_info',[]):
                candidate=public_v4(address.get('local',''))
                if candidate:return candidate
    except Exception:pass
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for url in ('https://api4.ipify.org','https://checkip.amazonaws.com'):
        try:
            with opener.open(url,timeout=5) as response:candidate=public_v4(response.read(64).decode())
            if candidate:return candidate
        except Exception:pass
    return '<服务器公网IP>'

def render(account,host):
    return '\n'.join([
        '\n========== XS-UI 安装完成 ==========',
        f"后台地址：http://{host}:{account['port']}/app/",
        f"后台端口：{account['port']}",
        f"管理员账号：{account['username']}",
        f"管理员密码：{account['password']}",
        '', '请在 VPS 服务商防火墙中放行：',
        f"TCP {account['port']}：后台管理",
        'TCP 80：Hysteria2 自动证书申请及续期',
        'UDP 443：Hysteria2 默认节点端口（TCP 443 不能代替）',
        'TCP 443：Reality 使用 443 时放行；如果页面分配了其他端口，放行实际端口',
        'SOCKS5：对外使用时放行你选择的 TCP 端口，并限制访问来源',
        '保留当前 SSH 端口；2096 为本机订阅服务，无需放行',
        '', '打开后台后：点击首页“一键创建节点”，填写域名、邮箱并生成。',
        '申请域名证书前，请把域名 A 记录指向本机公网 IP，使用仅 DNS 解析。',
        '后台初始为 HTTP；登录信息未加密，长期使用请在设置中配置 HTTPS。',
        '请保存账号密码，不要分享含密码的截图。',
        '初始凭据备份：/root/xs-ui-access.json（后台改密后，此文件不会自动更新）',
        '====================================',
    ])

if __name__=='__main__':
    print(render(json.loads(Path('/root/xs-ui-access.json').read_text()),detect_ip()))
