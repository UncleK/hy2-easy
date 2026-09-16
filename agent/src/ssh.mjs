import ssh2 from 'ssh2';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { isIP } from 'node:net';

const { Client } = ssh2;
export const root = fileURLToPath(new URL('../../', import.meta.url));
const quote = value => "'" + String(value).replaceAll("'", "'\\''") + "'";

export function validateInput(value) {
  const v = {...value};
  for (const name of ['host', 'publicHost']) {
    const host = String(v[name] || (name === 'publicHost' ? v.host : '')).trim().replace(/^\[|\]$/g, '');
    if (!(isIP(host) || (!/^[0-9.]+$/.test(host) && host.length <= 253 && host.split('.').every(s => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(s)))))
      throw new Error('请填写服务器 IP 或域名，不要填写网址或命令');
    v[name] = host;
  }
  if (!/^[a-z_][a-z0-9_-]{0,31}$/i.test(v.username || '')) throw new Error('SSH 用户名格式不正确');
  for (const name of ['sshPort', 'vpnPort']) {
    v[name] = Number(v[name] || (name === 'sshPort' ? 22 : 24443));
    if (!Number.isInteger(v[name]) || v[name] < (name === 'sshPort' ? 1 : 1024) || v[name] > 65535)
      throw new Error('端口格式不正确');
  }
  if (!!v.password === !!v.privateKey) throw new Error('请填写密码或选择私钥文件，只需一种');
  if (String(v.password || '').length > 4096 || String(v.privateKey || '').length > 65536)
    throw new Error('登录信息过长');
  return v;
}

function options(v) {
  return {host: v.host, port: v.sshPort, username: v.username,
    readyTimeout: 15000, keepaliveInterval: 10000, keepaliveCountMax: 3};
}
const fingerprint = key => 'SHA256:' + createHash('sha256').update(key).digest('base64').replace(/=+$/, '');

export function inspectHost(v) {
  return new Promise((resolve, reject) => {
    const c = new Client();
    c.on('error', () => { c.end(); reject(new Error('无法连接 SSH，请检查地址、SSH 端口和网络')); });
    c.connect({...options(v), hostVerifier: key => { const pin = fingerprint(key); resolve(pin); c.end(); return false; }});
  });
}

function connect(v, pin) {
  return new Promise((resolve, reject) => {
    const c = new Client();
    let mismatch = false;
    c.on('error', () => { c.end(); reject(new Error(mismatch ? '服务器 SSH 指纹发生变化，已停止连接' : 'SSH 登录失败，请检查用户名、密码或私钥')); });
    c.on('ready', () => resolve(c));
    c.connect({...options(v), password: v.password || undefined, privateKey: v.privateKey || undefined,
      passphrase: v.passphrase || undefined, hostVerifier: key => { mismatch = fingerprint(key) !== pin; return !mismatch; }});
  });
}

function exec(c, command, timeout = 600000) {
  return new Promise((resolve, reject) => {
    let stdout = '', size = 0;
    const timer = setTimeout(() => { c.end(); reject(new Error('服务器操作超时。安装可能仍在进行，请重新连接查看结果。')); }, timeout);
    c.exec(command, (err, stream) => {
      if (err) { clearTimeout(timer); reject(new Error('无法执行服务器操作')); return; }
      stream.on('data', data => {
        size += data.length;
        if (size > 1024 * 1024) { stream.close(); clearTimeout(timer); reject(new Error('服务器输出过长，已停止读取')); }
        else stdout += data;
      });
      stream.stderr.on('data', () => {}); // Never relay server-controlled output or credentials into chat/errors.
      stream.on('close', code => { clearTimeout(timer); resolve({code, stdout}); });
      stream.on('error', () => { clearTimeout(timer); reject(new Error('服务器连接中断')); });
    });
  });
}

function upload(c, path, contents) {
  return new Promise((resolve, reject) => c.sftp((err, sftp) => {
    if (err) return reject(new Error('服务器不支持 SFTP 上传'));
    const stream = sftp.createWriteStream(path, {mode: 0o600, flags: 'wx'});
    stream.on('error', () => { sftp.end(); reject(new Error('上传安装文件失败')); });
    stream.on('close', () => { sftp.end(); resolve(); });
    stream.end(contents);
  }));
}

export async function deploy(v, pin, progress) {
  const c = await connect(v, pin);
  let temp;
  try {
    const sudo = v.username === 'root' ? '' : 'sudo -n ';
    if ((await exec(c, sudo + 'true', 15000)).code !== 0) throw new Error('该用户不能免密码使用 sudo，请使用 root 或已配置免密码 sudo 的用户');
    progress('checking', '已登录，正在检查服务器');
    const exists = await exec(c, sudo + 'test -f /etc/hy2-easy/state.json', 15000);
    if (exists.code !== 0) {
      const made = await exec(c, 'umask 077; mktemp -d /tmp/hy2-easy-agent.XXXXXXXXXXXX', 15000);
      temp = made.stdout.trim();
      if (made.code !== 0 || !/^\/tmp\/hy2-easy-agent\.[a-zA-Z0-9]{12}$/.test(temp)) { temp = undefined; throw new Error('无法创建服务器临时目录'); }
      if ((await exec(c, 'mkdir ' + quote(temp + '/scripts'), 15000)).code !== 0) throw new Error('无法准备安装目录');
      await upload(c, temp + '/install.sh', await readFile(root + 'install.sh'));
      await upload(c, temp + '/scripts/hy2_easy.py', await readFile(root + 'scripts/hy2_easy.py'));
      progress('installing', '正在安装，通常需要几分钟。请保持 Agent 打开');
      const installed = await exec(c, `${sudo}bash ${quote(temp + '/install.sh')} --host ${quote(v.publicHost)} --port ${v.vpnPort} --no-share`);
      if (installed.code !== 0) throw new Error('安装未完成。请检查系统是否受支持、UDP 端口是否被占用，以及服务器能否访问 GitHub 和系统软件源。未覆盖已有配置');
    }
    if ((await exec(c, 'systemctl is-active --quiet hy2-easy.service', 15000)).code !== 0)
      throw new Error('检测到已有配置，但服务未运行；请在服务器运行 sudo hy2-easy 查看状态');
    // Use the bundled reader for compatibility with servers installed before --json was introduced.
    const read = await exec(c, sudo + "python3 -c " + quote("import json,pathlib; p=pathlib.Path('/etc/hy2-easy'); s=json.loads((p/'state.json').read_text()); assert s.get('owner')=='hy2-easy'; print(json.dumps({'uri':(p/'share.txt').read_text().strip(),'client':json.loads((p/'client.json').read_text())}))"), 15000);
    if (read.code !== 0) throw new Error('服务已运行，但未能读取连接信息');
    const result = JSON.parse(read.stdout);
    if (typeof result.uri !== 'string' || result.uri.length > 8192 || !result.client) throw new Error('服务器连接信息格式异常');
    return result;
  } finally {
    if (temp) await exec(c, `rm -f -- ${quote(temp + '/install.sh')} ${quote(temp + '/scripts/hy2_easy.py')}; rmdir -- ${quote(temp + '/scripts')} ${quote(temp)}`, 10000).catch(() => {});
    c.end();
  }
}
