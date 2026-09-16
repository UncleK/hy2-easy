# 验证记录

本项目区分本地服务启动、真实核心隧道、客户端图形界面和公网线路验证。

2026-09-16：本地 Debian 12 / amd64、真实 systemd 的隔离容器已通过下述安装与隧道测试。
测试使用实际上游二进制；错误密码与错误证书指纹均被拒绝。Git 历史另经 Gitleaks 8.30.1 扫描。

## 自动验证

- 单元测试：地址及 IPv6 链接编码、特殊字符密码、证书指纹约束、损坏下载拒绝、权限与覆盖保护、发布脚本校验和。
- Bash 语法与 ShellCheck。
- 一次性 Linux/systemd 容器：执行完整安装脚本，以真实 Hysteria 2.12.2 运行。
- 独立脚本下载分支：校验读取系统信息后仍使用正确的发布 URL 与源码 SHA-256。
  CI 只将固定标签源码请求映射到本次提交；核心二进制仍从上游真实下载。
- 从 PNG 解码二维码，核对与分享链接完全一致。
- 使用生成的客户端配置和分享 URI，各自通过真实 QUIC 隧道访问测试 HTTP 服务。
- 错误密码和错误证书指纹必须被真实核心拒绝。
- 检查服务账户权限、重启后的连接、重复安装保护、端口占用保护、卸载与启动失败回滚。

GitHub Actions 配置在 Debian 12/13、Ubuntu 22.04/24.04 的 amd64 环境运行；
另在 Debian 12 和 Ubuntu 24.04 的 arm64 环境运行。
各环境是否通过，以对应提交的 [Actions 结果](https://github.com/UncleK/hy2-easy/actions)为准。

## 复现

需要 Docker。以下命令创建并删除本项目专用测试容器；不要在现有 VPN 服务器上直接运行 `e2e.py`。
容器不映射公网端口，仓库只读挂载。

```bash
docker build -t hy2-easy-test -f tests/Dockerfile .
docker run -d --name hy2-easy-qa --privileged --cgroupns=private \
  --tmpfs /run --tmpfs /run/lock \
  --mount type=bind,source="$PWD",target=/src,readonly hy2-easy-test
docker exec hy2-easy-qa python3 -m unittest discover -s /src/tests -v
docker exec hy2-easy-qa python3 /src/tests/e2e.py --disposable-container
docker rm -f hy2-easy-qa
```

## 客户端与网络边界

v2rayN 的上游 `Hysteria2Fmt.ResolveHy2UriQuery` 实现会导入 `pinSHA256`。
这一源代码检查不等于 Windows/手机图形界面的扫码验收。
目前不声称所有第三方客户端、运营商线路或 IPv6 公网环境均已验证。

二维码解码和官方核心的 URI 连接已经纳入测试，但手机摄像头扫码、第三方客户端的实际证书校验行为，
仍需要在对应客户端版本与真实设备上验证。完整分享链接是使用前提。

本项目不会因服务显示 active 就宣称公网访问成功，也不将隔离环境测试当作公网吞吐或长期稳定性测试。
