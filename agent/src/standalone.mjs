#!/usr/bin/env node
import { createApp } from './app.mjs';
const app = await createApp();
const session = app.setup();
console.log(JSON.stringify({url: session.url, message: '在本机浏览器打开，配置完成前保持此进程运行。'}));
let printed = false;
const timer = setInterval(() => {
  try {
    const status = app.status(session.id);
    if (!printed && status.stage === 'done') {
      console.log(JSON.stringify({content: app.connection(session.id).content.filter(c => c.type === 'text')}));
      printed = true;
    }
  } catch { clearInterval(timer); app.close().then(() => process.exit(0)); }
}, 3000);
