import { createHash } from 'node:crypto';
import { mkdtemp, writeFile, chmod, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import net from 'node:net';
import http from 'node:http';
import tls from 'node:tls';
import { setTimeout as delay } from 'node:timers/promises';
import { mihomoProfile } from './catalog.mjs';

const execute = promisify(execFile);
const hashes = {
  'win32-x64': ['windows-amd64.exe', '807ae5332a8fefeeff804923e057b6942acceaa11706ac7fa3db42f192c2fde1'],
  'win32-arm64': ['windows-arm64.exe', '717feb36a44e67ef9e2db6a139f8004c6cb97c1aaf4eb7d03ce4710e6fc21165'],
  'linux-x64': ['linux-amd64', '6493dfffd55b5883f64c76c63880ecc32988f0c568c9ca9014907877b4d55f94'],
  'linux-arm64': ['linux-arm64', 'ebfacc1ec3a0edfd742cd68ce17f292a6092e606b9d11f99b035c1d888f3d709'],
  'darwin-x64': ['darwin-amd64', 'faea12f8e0fa9cb3ae9861fd7aff27bc2cebe136c07f0de63272eea0ec255900'],
  'darwin-arm64': ['darwin-arm64', 'd5850b02d0952ab5f88cd9bf37d0e84585905aba107e3f977336f1047f107d9d'],
};

export async function privateDirectory() {
  const dir = await mkdtemp(join(tmpdir(), 'hy2-easy-'));
  try {
    if (process.platform === 'win32') {
      const system = process.env.SystemRoot || 'C:\\Windows';
      // Build an exact DACL. Disabling inheritance alone can retain explicit ACEs
      // supplied by Windows on elevated runner/administrator-created directories.
      const script = `$ErrorActionPreference='Stop';
        $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User;
        $acl=[System.Security.AccessControl.DirectorySecurity]::new();
        $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true,$false);
        foreach($identity in @($sid,[System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'))){
          $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow');
          $acl.AddAccessRule($rule);
        }
        [System.IO.Directory]::SetAccessControl($env:HY2_PRIVATE_DIRECTORY,$acl);`;
      await execute(join(system, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe'),
        ['-NoProfile', '-NonInteractive', '-EncodedCommand', Buffer.from(script, 'utf16le').toString('base64')],
        {windowsHide: true, env: {...process.env, HY2_PRIVATE_DIRECTORY: dir}});
    } else await chmod(dir, 0o700);
    return dir;
  } catch (e) { await rm(dir, {recursive: true, force: true}); throw e; }
}

export async function downloadVerified(urls, expected, timeout = 90000) {
  for (const url of urls) {
    let bytes;
    try {
      if (!url.startsWith('https://')) throw new Error('仅允许 HTTPS 下载');
      // Handle redirects ourselves: never downgrade to HTTP or forward credentials.
      let target = url;
      const signal = AbortSignal.timeout(timeout);
      for (let hop = 0; hop < 6; hop++) {
        const response = await fetch(target, {signal, redirect: 'manual'});
        if ([301, 302, 303, 307, 308].includes(response.status)) {
          const next = new URL(response.headers.get('location'), target);
          if (next.protocol !== 'https:' || next.username || next.password) throw new Error('下载重定向无效');
          await response.body?.cancel(); target = next.href; continue;
        }
        if (!response.ok) { await response.body?.cancel(); throw new Error('下载失败'); }
        const chunks = []; let size = 0;
        for await (const chunk of response.body) {
          size += chunk.length;
          if (size > 100 * 1024 * 1024) throw new Error('下载文件超出限制');
          chunks.push(chunk);
        }
        bytes = Buffer.concat(chunks); break;
      }
      if (!bytes) throw new Error('重定向次数过多');
    } catch { continue; }
    if (createHash('sha256').update(bytes).digest('hex') !== expected)
      throw new Error('下载文件校验失败，未执行');
    return bytes;
  }
  throw new Error('无法下载连接检测组件；服务端安装不受影响');
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer(); s.on('error', reject);
    s.listen(0, '127.0.0.1', () => { const port = s.address().port; s.close(() => resolve(port)); });
  });
}

function throughProxy(port) {
  return new Promise((resolve, reject) => {
    const req = http.request({host: '127.0.0.1', port, method: 'CONNECT', path: 'www.gstatic.com:443'});
    let socket;
    const timer = setTimeout(() => { req.destroy(); socket?.destroy(); reject(new Error('连接检测超时')); }, 12000);
    const fail = error => { clearTimeout(timer); req.destroy(); socket?.destroy(); reject(error); };
    req.on('error', fail);
    req.on('connect', (res, raw, head) => {
      socket = raw;
      if (res.statusCode !== 200 || head.length) return fail(new Error('代理连接失败'));
      socket = tls.connect({socket: raw, servername: 'www.gstatic.com', rejectUnauthorized: true}, () => {
        socket.write('GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n');
      });
      let data = '';
      socket.on('error', fail);
      socket.on('data', chunk => {
        data += chunk.toString();
        if (data.includes('\r\n')) {
          clearTimeout(timer); socket.destroy();
          if (/^HTTP\/1\.[01] 204\b/.test(data)) resolve(); else reject(new Error('连接检测响应异常'));
        }
        if (data.length > 8192) fail(new Error('响应过长'));
      });
    });
    req.end();
  });
}

export async function verifyConnection(uri) {
  const proxy = JSON.parse(mihomoProfile(uri)).proxies[0];
  const selected = hashes[`${process.platform}-${process.arch}`];
  if (!selected) return {verified: false, message: '当前电脑架构不支持自动检测，请导入客户端后连接'};
  let dir, child, phase = 'private-directory';
  try {
    dir = await privateDirectory();
    const [asset, hash] = selected;
    phase = 'download';
    const bytes = await downloadVerified([
      `https://github.com/HyNetworks/hysteria/releases/download/app/v2.12.2/hysteria-${asset}`,
      `https://agentschat.app/hy2-easy-downloads/hysteria-2.12.2/hysteria-${asset}`
    ], hash, 30000);
    const binary = join(dir, process.platform === 'win32' ? 'hysteria.exe' : 'hysteria');
    await writeFile(binary, bytes, {flag: 'wx', mode: 0o700});
    const port = await freePort();
    phase = 'client-start';
    const config = {server: `${proxy.server.includes(':') ? '[' + proxy.server + ']' : proxy.server}:${proxy.port}`,
      auth: proxy.password, tls: {sni: proxy.sni, insecure: true, pinSHA256: proxy.fingerprint},
      http: {listen: `127.0.0.1:${port}`}};
    const configPath = join(dir, 'probe.json');
    await writeFile(configPath, JSON.stringify(config), {flag: 'wx', mode: 0o600});
    child = spawn(binary, ['client', '--disable-update-check', '--config', configPath], {stdio: 'ignore', windowsHide: true});
    let failed = false; child.on('error', () => { failed = true; });
    await delay(1500);
    if (failed || child.exitCode !== null) throw new Error('检测组件未能启动');
    phase = 'tunnel';
    await throughProxy(port);
    return {verified: true, message: '已从这台电脑通过 VPN 完成联网检测'};
  } catch {
    return {verified: false, reason: phase, message: phase === 'download'
      ? '服务已运行，但未能下载自动检测组件。可以先扫码或复制链接，在客户端尝试连接'
      : '服务已运行，自动联网检测未通过。请确认云服务器已放行 UDP 端口，再导入客户端尝试连接'};
  } finally {
    if (child?.pid && child.exitCode === null) {
      await new Promise(resolve => { child.once('exit', resolve); child.kill(); setTimeout(resolve, 3000).unref(); });
    }
    if (dir) await rm(dir, {recursive: true, force: true, maxRetries: 3, retryDelay: 300});
  }
}
