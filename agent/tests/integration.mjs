// Run only against the disposable sshd/systemd container documented in docs/verification.md.
import assert from 'node:assert/strict';
import { createApp } from '../src/app.mjs';
import { deploy } from '../src/ssh.mjs';
import { execFileSync } from 'node:child_process';
if (!process.argv.includes('--disposable-container')) throw new Error('Explicit disposable-container flag required');
const app = await createApp();
try {
  const s = app.setup(); const token = new URL(s.url).hash.slice(1);
  const call = async (path, body) => {
    const r = await fetch(app.origin + '/api/' + path, {method: body ? 'POST' : 'GET',
      headers: {Origin: app.origin, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
    const data = await r.json(); assert.ok(r.ok, data.error); return data;
  };
  const input = {host: '127.0.0.1', sshPort: 22222, publicHost: '127.0.0.1', vpnPort: 24444,
    username: 'root', password: 'hy2-easy-disposable-test'};
  const inspected = await call('inspect', input); assert.match(inspected.fingerprint, /^SHA256:/);
  await assert.rejects(deploy(input, 'SHA256:wrong', () => {}), /指纹/);
  await call('install', {...input, fingerprint: inspected.fingerprint});
  let state, previous;
  for (let i = 0; i < 480; i++) {
    state = app.status(s.id);
    if (state.stage !== previous) { console.log('Stage:', state.stage); previous = state.stage; }
    if (['done', 'error'].includes(state.stage)) break;
    await new Promise(r => setTimeout(r, 2000));
  }
  assert.equal(state.stage, 'done', state.message);
  assert.equal(state.verified, true, state.message);
  const result = app.connection(s.id);
  assert.ok(result.content.some(c => c.type === 'image'));
  const png = Buffer.from(result.content.find(c => c.type === 'image').data, 'base64');
  const decoded = execFileSync('docker', ['exec', '-i', 'hy2-easy-agent-qa', 'python3', '-c',
    "import sys,tempfile,subprocess; f=tempfile.NamedTemporaryFile(); f.write(sys.stdin.buffer.read()); f.flush(); print(subprocess.check_output(['zbarimg','--quiet','--raw',f.name],stderr=subprocess.DEVNULL).decode(),end='')"], {input: png, encoding: 'utf8'}).trim();
  assert.equal(decoded, JSON.parse(result.content[0].text).uri);
  assert.ok(!JSON.stringify(result).includes(input.password));
  console.log('PASS: SSH wrong host pin rejected; local form -> isolated install -> real QUIC HTTPS -> decoded MCP QR');
} finally { await app.close(); }
