# XS-UI · 私人开发测试版

基于 [S-UI](https://github.com/alireza0/s-ui) v1.6.7 和配套前端开发。目标是在原面板中快捷创建 Hysteria2、VLESS + Reality + Vision、带认证的 SOCKS5，供个人测试及使用。保留 GPLv3 许可证与上游署名。

**当前状态：dev.2，尚未通过真实 VPS 安装与代理链路验收。不要替换正在使用的 S-UI。** 仓库和 Release 尚未由开发环境上传，本文命令只有在对应内容实际发布后才有效。

## 已做好的内容

- 原入站页面新增“快捷创建节点”，自动生成强随机凭据和导入链接。
- Hysteria2 支持填写域名、邮箱后自动申请/续期证书；Reality 自动生成密钥、UUID、Short ID；不关闭客户端证书校验。
- 先保存停用节点，读回核对凭据及绑定，再提交启用；创建前后检查核心状态。失败不自动重复写入。
- SOCKS5 默认仅在服务器本机监听。外部访问需明确开启并限制防火墙来源；普通 SOCKS5 本身不加密。
- 独立低权限服务账号；后台与订阅默认仅监听 127.0.0.1；随机管理员凭据写入 root 专用文件。
- 安装时检测内核 TCP BBR。内核支持则启用并保存原值；不支持则跳过，不换内核、不重启。修改失败尝试恢复运行时原值，安装报错停止。
- 安装后检查登录、核心运行、后台和订阅端口是否仅在本机监听。此检查不等于公网节点已可连接。
- 私有 GitHub Release 下载入口，校验压缩包 SHA-256，拒绝路径穿越、链接和非预期文件。

目前安装器接受 **Ubuntu/Debian、x86_64、systemd**，仍待实机验证具体版本。其他发行版、ARM64 没有发行包，会明确退出。不会在 768 MB VPS 上现场编译。

## 使用前先看

1. [安装、私有仓库发布和访问方法](docs/INSTALL_ZH.md)
2. [安全范围与实机验收](docs/SECURITY_AND_ACCEPTANCE.md)
3. [测试记录](TEST_REPORT.md)
4. [构建来源](BASELINES.json)

不设置额外节点带宽上限。Hysteria2 的 QUIC 拥塞控制与 Linux TCP BBR 是不同层面的机制；开启系统 BBR 不代表 Hysteria2 一定提速，也无法保证线路跑满 100 Mbps。

## 开发与构建

源文件位于 `backend/`、`frontend/`。当前预编译程序沿用 dev.1 已验证构建，本轮仅更新发行包安装工具及文档。网页仍保留 S-UI 上游标识，未宣称完成所有品牌替换。

```bash
cd frontend
npm ci
npm test
npm run build
cd ..
bash backend/quick-node/build-package.sh "$PWD/frontend" "$PWD/release/package"
```

需要与 `backend/go.mod` 一致的 Go 工具链，以及可用的 C 编译器。使用的最小构建标签为 `with_quic,with_utls,with_acme,netgo,osusergo,sqlite_omit_load_extension`。TUN/TProxy、Naive、Tailscale 等可选功能不在这版构建支持范围。不要通过原版自动升级覆盖本分支。

本项目没有完成独立安全审计，不能承诺绝对不会被入侵。私有仓库限制源码访问，不代替 VPS 的身份认证和系统维护。
