#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { createApp } from './app.mjs';
import { downloads } from './catalog.mjs';

const app = await createApp();
const server = new McpServer({name: 'hy2-easy', version: '0.2.0'});
const text = value => ({content: [{type: 'text', text: JSON.stringify(value)}]});
const call = fn => async args => { try { return await fn(args); } catch (e) { return {...text({error: e.message}), isError: true}; } };
server.registerTool('hy2_setup', {description: '打开本机 SSH 配置表单。用户填写服务器信息并点击安装后，自动部署个人 Hysteria 2 VPN。不要在聊天中索取密码或私钥。仅适用于 MCP 运行在用户本机的 Agent。', inputSchema: {}, annotations: {destructiveHint: false}}, call(() => text(app.setup())));
server.registerTool('hy2_status', {description: '查询安装进度。调用立即返回；间隔约 5 秒查询，done 后获取连接二维码。', inputSchema: {id: z.string().uuid()}, annotations: {readOnlyHint: true}}, call(({id}) => text(app.status(id))));
server.registerTool('hy2_connection', {description: '安装完成后返回用户授权显示的 VPN 链接及二维码图片。不支持图片的 Agent 应保留本机配置页入口。不要把二维码上传公共图床。', inputSchema: {id: z.string().uuid()}, annotations: {readOnlyHint: true}}, call(({id}) => app.connection(id)));
server.registerTool('hy2_downloads', {description: '获取客户端官方优先下载链接、版本和校验值。只展示实际返回的备份链接。', inputSchema: {}, annotations: {readOnlyHint: true}}, call(() => text(downloads)));
await server.connect(new StdioServerTransport());
process.stdin.on('end', () => process.exit(0));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => process.exit(0));
