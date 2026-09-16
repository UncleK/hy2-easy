# 让 Agent 帮你配置

你需要一台自己的云服务器，以及能执行本地工具的 Agent。SSH 登录在本机小页面里完成，不需要另外下载 SSH 软件，也不用把密码粘贴到聊天。

复制下面这段话给 Agent：

```text
帮我用 hy2-easy 配置自己的 VPN，请先阅读：
https://github.com/UncleK/hy2-easy/blob/main/docs/agent.md

打开本机页面，让我填写服务器登录信息，不要在聊天里索取密码或私钥。
配置完成后，给我二维码、连接链接和客户端下载链接。
```

然后跟着 Agent 给出的链接填写。第一次连接会显示服务器 SSH 指纹；在云服务商控制台核对并确认后，点“开始配置”。通常等几分钟，页面和支持图片的 Agent 就能显示二维码。扫码用 VPN 客户端里的扫一扫；在同一台设备上就复制链接导入。

云服务器要允许 **UDP 24443** 入站。工具会检测连接，但无法替你登录云服务商控制台修改安全组。

## 给 Agent 的接入说明

下载固定版本分发包：

- [GitHub：hy2-easy-agent-v0.2.1.zip](https://github.com/UncleK/hy2-easy/releases/download/v0.2.1/hy2-easy-agent-v0.2.1.zip)
- [服务器备份与校验值（当前为 0.2.0，保留旧版显示勾选项）](https://agentschat.app/hy2-easy-downloads/)

解压后得到 `hy2-easy` 目录。里面已包含 npm 运行依赖，不需要现场访问 npm 安装。使用宿主提供的 Node.js 20+ 执行 `node agent/configure.mjs`，它会生成符合当前解压位置的配置文件：

| Agent 能力 | 使用方式 |
| --- | --- |
| DSH | 将 `agent/configured/dsh-plugins.yaml` 中的插件项合入所用 profile 的插件配置，保持原配置其他项。需要 `@deepseek-ai/dsh-mcp-client` 插件可用。 |
| WorkBuddy 5.0+ | 使用 `agent/configured/workbuddy` 目录中的连接器配置；其中声明托管 Node 22 运行时。也可在本地 MCP 设置中使用生成的 `mcp.json`。 |
| 其他本地 MCP Agent | 按该宿主的配置格式导入 `agent/configured/mcp.json` 中的 stdio 命令和参数。 |
| 只有本地终端执行能力 | 后台运行 `node agent/src/standalone.mjs`，将输出的本机链接交给用户；保持进程存活。页面显示二维码，完成后的终端输出返回连接链接与页面地址，由 Agent 展示给用户。 |

宿主缺少 Node 时，应先检查其托管运行时。WorkBuddy 的 MCP 配置可使用它自己的托管 Node；生成配置前也可由 Agent 直接把 `command=node`、`args=[解压后 agent/src/mcp.mjs 的绝对路径]` 填入本地 MCP 设置。不能假设所有 Agent 都自带 Node。

通用 Skill 在 `agent/adapters/skills/hy2-easy/SKILL.md`。按宿主支持的方式加载；四个 MCP 工具已经包含基本使用描述，不加载 Skill 也能按工具返回值工作。

MCP 工具为 `hy2_setup`、`hy2_status`、`hy2_connection`、`hy2_downloads`。安装在后台进行，查询立即返回。不要通过重启 MCP 来等待安装，不要把服务 `active` 当作端到端联网成功。仅当返回 `verified=true`，才说当前电脑的 VPN 联网检测通过。

`hy2_setup` 只创建本机入口；实际 SSH 和安装必须由用户在页面确认后触发。工具会复用已有 hy2-easy 配置；不会覆盖其他 VPN、修改防火墙或重启其他业务。全新安装支持 Debian 12/13、Ubuntu 22.04/24.04 的 amd64/arm64，root 或免密码 sudo。

## 已验证到哪里

标准 MCP 协议、安装工具和本机页面有自动化验证。DSH、WorkBuddy 提供按其文档生成的接入配置，**未完成这两个产品的端到端 UI 验收**；图片显示仍取决于模型和宿主。DSH 的 MCP 桥接在图片能力不可用时可能只显示提示，这时使用本机扫码页。

普通豆包聊天或纯云端 Agent 不一定能运行本机工具，不能保证自动配置；云端机器上的 `127.0.0.1` 也不是用户的电脑。SSH 表单服务必须运行在用户本机。不要把它监听到公网。

GitHub 和海外服务器备份在不同网络下的可访问性不同，当前未验证中国大陆无代理环境。
