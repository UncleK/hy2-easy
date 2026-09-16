// Documentation-only preview. Uses the real UI with fictional data, never SSH.
import { createApp } from '../agent/src/app.mjs';
if (!process.argv.includes('--demo')) throw new Error('Use --demo for the fictional documentation preview');
let finish;
const gate = new Promise(resolve => { finish = resolve; });
const uri = 'hysteria2://documentation-only@example.invalid:24443/?sni=hy2-easy.local&insecure=1&pinSHA256=' + 'ab'.repeat(32) + '#hy2-easy-demo';
const app = await createApp({
  inspectHost: async () => 'SHA256:DEMO-ONLY-check-your-own-server-fingerprint',
  deploy: async (_input, _pin, progress) => {
    progress('installing', '正在安装，通常需要几分钟。请保持 Agent 打开');
    await gate;
    return {uri};
  },
  verifyConnection: async () => ({verified: true, message: '演示截图：此二维码不能用于连接，请使用你自己页面中的连接信息。'})
});
console.log('Documentation demo only. No SSH connection or VPN installation will occur.');
console.log(app.setup().url);
console.log('Send any line on stdin after capturing the progress screen to show the demo result.');
process.stdin.on('data', () => finish());
process.on('SIGINT', () => process.exit(0));
