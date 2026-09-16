# 维护

hy2-easy 0.1.1 安装 Hysteria 2.12.2，只管理它自己的路径与服务。

| 路径 | 用途 |
| --- | --- |
| `/usr/local/bin/hy2-easy` | 管理命令 |
| `/usr/local/lib/hy2-easy/hysteria` | 校验过的上游核心 |
| `/etc/hy2-easy/server.json` | 服务端配置 |
| `/etc/hy2-easy/server.crt`、`server.key` | 证书与私钥 |
| `/etc/hy2-easy/share.txt`、`share.png` | 私密连接链接与二维码 |
| `/etc/hy2-easy/client.json` | 可供官方 Hysteria 客户端使用的配置 |
| `/etc/hy2-easy/state.json` | 本机安装记录 |
| `/etc/systemd/system/hy2-easy.service` | systemd 服务 |

安装会通过 apt 安装 `ca-certificates`、`curl`、`python3`、`openssl`、`qrencode`、`passwd`，
创建 `hy2-easy` 系统用户，并启用开机启动。
不会自动修改防火墙、SSH、现有代理服务、内核网络参数或客户端设置。
默认 UDP 24443 必须由服务器所有者在云安全组和主机防火墙放行。

## 重复安装与失败

检测到已有安装文件、同名用户/组或端口占用时停止，不覆盖原有配置。
下载阶段失败不创建服务；服务安装阶段失败会回滚本次创建的服务、文件和用户。
已安装的 apt 依赖会保留。

再次查看连接信息：

```bash
sudo hy2-easy share
```

也可以运行 `sudo hy2-easy` 打开中文菜单，输入数字完成相应操作。

服务处于 active 只说明本机进程运行；公网 UDP 可达性与客户端连接需要从用户设备验证。

## 备份

需要保留节点身份时，对 `/etc/hy2-easy/` 做私密、加密备份。不要提交到 Git 或公开 Issue。
`server.key`、`server.json`、分享文件和客户端配置包含秘密。

0.1.1 不提供自动升级或覆盖迁移。后续版本将提供明确的升级说明。
从原 `hysteria-server.service` 迁移时，不要直接覆盖其文件或卸载原服务；本项目使用独立路径，
可先在另一空闲端口验证，再自行决定是否切换。旧部署资料可从 Git 历史查阅。

## 卸载

```bash
sudo hy2-easy uninstall
```

输入 `DELETE` 后，停止并禁用服务，删除本项目安装的配置、证书、分享文件、核心和系统用户。
自动化环境可使用 `sudo hy2-easy uninstall --yes`。
系统依赖、防火墙规则和其他服务不会被删除。

卸载后重装会生成新的密码和证书，客户端需要重新导入。

## 直接使用官方客户端

将 `/etc/hy2-easy/client.json` 私密复制到客户端机器，使用同版本 Hysteria 运行：

```bash
hysteria client --disable-update-check --config client.json
```

默认仅监听本机 SOCKS5 `127.0.0.1:1080` 和 HTTP `127.0.0.1:8080`。
这份文件供高级使用与排错；普通用户使用分享链接即可。
