# XS-UI dev.2 验证记录

记录日期：2026-11-16。不是独立安全审计或生产可用证明。

| 检查 | 结果 |
|---|---|
| BBR 设置器测试（本轮） | 4 项通过：启用/重复执行保留原备份、内核不支持时跳过、部分失败恢复、拒绝覆盖外部文件；使用模拟命令，未修改开发机内核 |
| 安装后端口检查测试（本轮） | 4 项通过：允许本地监听、拒绝 IPv4/IPv6 公网监听、缺失订阅监听拒绝、额外公网绑定拒绝 |
| Release 校验解压测试（本轮） | 6 项通过：正常包、校验错误、路径穿越、符号/硬链接、重复文件、未知文件 |
| Bash 语法 | 安装入口、本地安装器、构建器及只读检查脚本通过 |
| 前端（dev.1，同一源代码与二进制） | 157 项测试通过，其中快捷创建相关 24 项；类型检查和 Vite 构建通过 |
| 后端（dev.1，同一源代码与二进制） | cmd、api、service、database、database/model、util 相关测试通过；内联 ACME 核心解析/构造测试通过，未请求真实证书 |
| 真实 API（dev.1） | 最终二进制验证登录拒绝、跨站写入拒绝、Reality 密钥生成、三协议 TLS/账号/停用入站保存、凭据绑定、停用节点不进入核心配置 |
| 完整本地代理与浏览器 | 环境限制阻塞：核心 netlink socket、Chromium Unix socket 权限不允许；未绕过限制，未声称通过 |
| systemd/Ubuntu/Debian 实机安装 | 未验证；当前只有发行版/架构检查与安装器设计，不代表所有版本都兼容 |
| BBR 实机生效/重启持久性 | 未验证 |
| 公开证书、三协议连通、PassWall2、性能 | 未验证 |
| GitHub 上传与私有 Release 下载 | 未完成；账号流程受限，未发布 Release |

dev.2 未改动 Go 应用或 Vue 前端，沿用 dev.1 最终静态 Linux x86_64 二进制；变更为 XS-UI 服务安装命名、BBR、启动检查、发行包入口、测试及说明文档。二进制 SHA-256：

`3d4773af70a1aa272fe4a595bb347cf02472376d8d10bc35d497918df9e2ce8e`

## 本轮复核命令

```bash
python3 backend/quick-node/test_configure_bbr.py
python3 backend/quick-node/test_verify_install.py
python3 tools/test_verify_release.py
bash -n install.sh backend/quick-node/install-local.sh backend/quick-node/build-package.sh tools/preflight.sh
```

前轮应用测试方法详见 backend/quick-node/smoke-local.py 和前端测试文件。实际服务器不能用 `--api-only` 的成功代替代理连接验收。
