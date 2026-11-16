# XS-UI · v0.1.0-dev.3

基于 S-UI v1.6.7 的个人面板。保留 GPLv3 许可证与上游署名。

## 安装后就能打开公网后台

- 面板默认监听公网 IPv4 的 TCP 2095，路径 /app/。不需要 SSH 隧道。
- 安装完成直接显示公网地址、端口、随机账号、随机密码和防火墙放行清单。
- 安装脚本自动安装依赖、校验下载包、初始化专用低权限服务、检测并启用可用的 BBR。
- 公开仓库直接下载安装，不需要 Git/GitHub CLI 或登录授权。
- 已有 XS-UI 的机器不会被覆盖；这版安装入口面向空白新 VPS。

## 一条命令安装

先将 Bapai6268/XS-UI 设为 Public，并发布本版本附件。然后在新 VPS 的 SSH 终端执行以下一整行：

```bash
bash -c 'set -e; s=(); [ "$(id -u)" -eq 0 ] || s=(sudo); command -v curl >/dev/null || { "${s[@]}" apt-get update; "${s[@]}" apt-get install -y curl ca-certificates; }; f=$(mktemp); trap "rm -f -- \"$f\"" EXIT; curl -fsSL https://raw.githubusercontent.com/Bapai6268/XS-UI/main/install.sh -o "$f"; "${s[@]}" bash "$f"'
```

命令支持 root 或具备 sudo 权限的普通用户；普通用户可能需要输入一次系统 sudo 密码。推荐 Ubuntu 24.04 x86_64；安装器接受 Ubuntu/Debian + x86_64 + systemd，其他系统会明确退出。本包尚未在 LAX-CUPN Lite 实机验收。

## 进入后台后

首页有“一键创建节点”按钮，入站页仍有“快捷创建节点”。服务器地址默认填入当前访问地址，填写域名后自动带入证书域名。

Hysteria2：将子域名 A 记录指向 VPS 公网 IPv4，保持“仅 DNS”；输入域名、联系邮箱，确认 TCP 80 可用和证书条款后生成。证书由核心自动申请及续期，不跳过验证。首次写入成功不等于签发完成，请看首页日志。

Reality：输入适用且服务器可达的 TLS 1.3 目标域名；密钥、UUID、Short ID 自动生成。

SOCKS5：自动生成认证账号，默认仅本机；需要指纹浏览器直接连接时打开“允许外部连接”，限制防火墙来源，使用实际端口。普通 SOCKS5 不加密。

节点不添加人为带宽上限。系统 TCP BBR 与 Hysteria2 自身拥塞控制不同，不能保证线路跑满 100 Mbps。

## 防火墙端口

| 用途 | 放行 |
|---|---|
| 后台 | TCP 2095 |
| 自动证书 | TCP 80 |
| Hysteria2 默认端口 | UDP 443 |
| Reality | 实际节点 TCP 端口，通常为 443；若面板自动分配其他端口，以页面为准 |
| 外部 SOCKS5 | 实际配置的 TCP 端口，并限制来源 |
| SSH | 保留当前 SSH 端口 |

安装器会给已启用的 UFW 或 firewalld 默认区域添加上述默认端口，不启用新防火墙，不清空原规则。服务商云防火墙由你手动放行，自定义主机防火墙需要按实际规则处理。订阅 2096 仅本机监听，无需开放。

## 凭据与安全范围

后台初始 HTTP 是用户要求的公网直接访问模式，登录信息未加密；长期使用需配置 HTTPS。这个版本没有实现后台 HTTPS 的全自动签发/部署，不宣称已经解决该项。

账号密码安装完成直接显示，初始凭据备份在 /root/xs-ui-access.json，仅 root 可读。后台改密后该文件仍是初始凭据，不会同步更新。密码和证书私钥不打包到 GitHub。私有/公开切换不影响已安装服务，但公开期间的副本无法收回。

服务使用 xs-ui 低权限用户，仅授予绑定低端口能力。完整安全审计、外网证书/续期、PassWall2 连通性、768 MB 性能仍需实机验收。不要用原版 S-UI 自动升级覆盖该分支。

构建源码位于 frontend/ 和 backend/，构建脚本为 backend/quick-node/build-package.sh；最小标签为 with_quic,with_utls,with_acme,netgo,osusergo,sqlite_omit_load_extension。Naive/TUN/Tailscale 等不在本版本支持范围。
