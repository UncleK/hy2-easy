import { createServer } from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import QRCode from 'qrcode';
import { downloads, mihomoProfile } from './catalog.mjs';
import { inspectHost, deploy, validateInput } from './ssh.mjs';
import { verifyConnection } from './verify.mjs';

const assets = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']],
]);
export async function createApp(backend = {inspectHost, deploy, verifyConnection}, ttl = 30 * 60 * 1000) {
  const sessions = new Map();
  let origin;
  const view = s => ({id: s.id, stage: s.stage, message: s.message, fingerprint: s.fingerprint,
    verified: s.verified, downloads, expiresAt: s.expiresAt});
  const active = s => ['probing', 'checking', 'installing', 'verifying'].includes(s.stage);
  const server = createServer(async (req, res) => {
    const send = (status, value, type = 'application/json; charset=utf-8') => {
      res.writeHead(status, {'Content-Type': type});
      res.end(type.startsWith('application/json') ? JSON.stringify(value) : value);
    };
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
    try {
      if (req.headers.host !== new URL(origin).host || (req.headers.origin && req.headers.origin !== origin)) return send(403, {error: '请使用 Agent 给出的本机链接打开'});
      if (req.method === 'GET' && req.url === '/favicon.ico') { res.writeHead(204); return res.end(); }
      if (req.method === 'GET' && assets.has(req.url)) {
        const [file, type] = assets.get(req.url);
        return send(200, await readFile(new URL('../ui/' + file, import.meta.url)), type);
      }
      const session = [...sessions.values()].find(s => req.headers.authorization === 'Bearer ' + s.token);
      if (!session || (!active(session) && session.expiresAt < Date.now())) return send(401, {error: '此配置页面已过期，请让 Agent 重新打开'});
      if (req.method === 'GET' && req.url === '/api/status') return send(200, view(session));
      if (req.method === 'GET' && req.url === '/api/result') {
        if (!session.result) return send(409, {error: '连接信息还未准备好'});
        return send(200, {...view(session), uri: session.result.uri, qr: session.qr,
          mihomo: mihomoProfile(session.result.uri)});
      }
      if (req.method !== 'POST' || req.headers.origin !== origin || req.headers['content-type'] !== 'application/json') return send(403, {error: '请求来源无效'});
      let body = ''; for await (const chunk of req) { body += chunk; if (Buffer.byteLength(body) > 80000) return send(413, {error: '提交内容过长'}); }
      const value = JSON.parse(body);
      if (req.url === '/api/inspect') {
        if (active(session) || session.result) return send(409, {error: '已有操作正在进行或已完成'});
        const input = validateInput(value);
        session.stage = 'probing'; session.message = '正在确认服务器身份';
        // Credentials never enter the session, tool response, logs or disk before the user trusts the host.
        session.fingerprint = await backend.inspectHost(input);
        session.host = input.host; session.sshPort = input.sshPort;
        session.stage = 'trust'; session.message = '请确认这是你的服务器';
        return send(200, view(session));
      }
      if (req.url === '/api/install') {
        if (session.stage !== 'trust' || value.fingerprint !== session.fingerprint) return send(409, {error: '请先确认服务器指纹'});
        const input = validateInput(value);
        if (input.host !== session.host || input.sshPort !== session.sshPort) return send(409, {error: '地址已修改，请重新检查服务器身份'});
        session.stage = 'checking'; session.message = '正在登录服务器';
        const progress = (stage, message) => { session.stage = stage; session.message = message; };
        // Reply immediately so MCP/UI calls never wait for package installation.
        session.job = (async () => {
          try {
            const result = await backend.deploy(input, session.fingerprint, progress);
            mihomoProfile(result.uri); // Validate and construct only known fields, never execute server-supplied client config.
            session.result = {uri: result.uri};
            session.qr = await QRCode.toDataURL(result.uri, {width: 360, margin: 4, errorCorrectionLevel: 'M'});
            progress('verifying', '服务已运行，正在从当前电脑检测连接');
            const check = await backend.verifyConnection(result.uri);
            session.verified = check.verified;
            progress('done', check.message);
          } catch (e) { session.stage = 'error'; session.message = safeError(e); }
          finally { input.password = input.privateKey = input.passphrase = undefined; session.expiresAt = Date.now() + ttl; }
        })();
        return send(202, view(session));
      }
      return send(404, {error: '页面不存在'});
    } catch (e) {
      const s = [...sessions.values()].find(s => req.headers.authorization === 'Bearer ' + s.token);
      if (s?.stage === 'probing') { s.stage = 'error'; s.message = safeError(e); }
      return send(400, {error: safeError(e)});
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
  const timer = setInterval(() => {
    for (const [id, session] of sessions) if (!active(session) && session.expiresAt < Date.now()) sessions.delete(id);
  }, 30000); timer.unref();
  return {
    origin,
    setup() {
      if (sessions.size >= 8) throw new Error('打开的配置页过多，请稍后再试');
      const s = {id: randomUUID(), token: randomBytes(32).toString('hex'), stage: 'ready', message: '请填写服务器登录信息', expiresAt: Date.now() + ttl};
      sessions.set(s.id, s);
      return {...view(s), url: `${origin}/#${s.token}`};
    },
    status(id) { const s = sessions.get(id); if (!s || (!active(s) && s.expiresAt < Date.now())) throw new Error('配置已过期，请重新打开'); return view(s); },
    connection(id) {
      this.status(id); const s = sessions.get(id);
      if (!s.result || s.stage !== 'done') throw new Error('安装或检测尚未完成，请稍后查询状态');
      return {content: [{type: 'text', text: JSON.stringify({...view(s), uri: s.result.uri,
        page: `${origin}/#${s.token}`, note: '二维码和链接是 VPN 凭据；请勿上传公共图床。Mihomo 配置可在本机页面下载。'})},
        {type: 'image', mimeType: 'image/png', data: s.qr.split(',')[1], annotations: {audience: ['user']}}]};
    },
    async close() { clearInterval(timer); sessions.clear(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  };
}

function safeError(e) {
  // Only errors authored by this application are presented; library exceptions can contain credentials.
  const text = String(e?.message || '');
  return /^[\u3400-\u9fff]/.test(text) && text.length < 250 ? text : '操作未完成，请检查填写内容或重新打开配置页';
}
