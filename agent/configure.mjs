#!/usr/bin/env node
// Run from an extracted bundle. Generates absolute paths for this installation only.
import { mkdir, writeFile, cp } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const directory = dirname(fileURLToPath(import.meta.url));
const entry = join(directory, 'src', 'mcp.mjs');
const out = join(directory, 'configured');
await mkdir(out, {recursive: true});
const generic = {mcpServers: {'hy2-easy': {command: process.execPath, args: [entry]}}};
await writeFile(join(out, 'mcp.json'), JSON.stringify(generic, null, 2));
const dsh = [{id: 'mcp-hy2-easy', name: '@deepseek-ai/dsh-mcp-client', config: {
  serverName: 'hy2-easy', transport: 'stdio', command: process.execPath, args: [entry], toolCallTimeoutMs: 30000}}];
// JSON is valid YAML and avoids escaping Windows paths incorrectly.
await writeFile(join(out, 'dsh-plugins.yaml'), JSON.stringify(dsh, null, 2));
const wb = join(out, 'workbuddy');
await mkdir(wb, {recursive: true});
await writeFile(join(wb, 'mcp.json'), JSON.stringify({mcpServers: {'hy2-easy': {
  type: 'stdio', command: 'node', args: [entry], runtime: {type: 'node', version: '22'}}}}, null, 2));
await writeFile(join(wb, 'connector-meta.json'), JSON.stringify({
  name: 'hy2-easy', name_zh: 'hy2-easy', name_en: 'hy2-easy', source: 'hy2-easy', type: 'mcp', version: '0.2.0',
  description: 'Set up a personal Hysteria 2 VPN with a local SSH form, then scan the QR code to connect.',
  description_zh: '在本机填写服务器登录信息，自动配置个人 Hysteria 2 VPN，完成后扫码或复制链接连接。',
  description_en: 'Set up a personal Hysteria 2 VPN with a local SSH form, then scan the QR code to connect.',
  examples_zh: ['帮我配置自己的 VPN', '给我连接二维码和客户端下载链接'],
  examples_en: ['Set up my personal VPN', 'Show my connection QR code and client downloads'], minWorkbuddyVersion: '5.0.0'
}, null, 2));
await writeFile(join(wb, 'icon.svg'), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#175c48"/><text x="32" y="44" text-anchor="middle" font-size="42" fill="white">h₂</text></svg>');
await cp(join(directory, 'adapters', 'skills'), join(wb, 'skills'), {recursive: true});
console.log(JSON.stringify({generic: join(out, 'mcp.json'), dsh: join(out, 'dsh-plugins.yaml'), workbuddy: wb}));
