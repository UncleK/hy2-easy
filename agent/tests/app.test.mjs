import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.mjs';
import { validateInput } from '../src/ssh.mjs';
import { mihomoProfile } from '../src/catalog.mjs';
import { privateDirectory, downloadVerified } from '../src/verify.mjs';
import { rm, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import http from 'node:http';

const uri = 'hysteria2://test-only%3A%40%2F@127.0.0.1:24443/?sni=hy2-easy.local&insecure=1&pinSHA256=' + 'ab'.repeat(32) + '#hy2-easy';
const input = {host: '127.0.0.1', username: 'root', password: 'test-only-secret'};
test('local form, host trust, async job and matching web/Agent connection results', async () => {
  let deployed = 0, release;
  const gate = new Promise(r => { release = r; });
  const app = await createApp({inspectHost: async () => 'SHA256:test-only', deploy: async (value, pin) => {
    assert.equal(value.password, input.password); assert.equal(pin, 'SHA256:test-only'); deployed++; await gate; return {uri};
  }, verifyConnection: async () => ({verified: true, message: '通过'})});
  try {
    const s = app.setup(); const token = new URL(s.url).hash.slice(1);
    const request = (path, body, overrides = {}) => fetch(app.origin + '/api/' + path, {
      method: body ? 'POST' : 'GET', headers: {Authorization: 'Bearer ' + token, Origin: app.origin, 'Content-Type': 'application/json', ...overrides}, body: body ? JSON.stringify(body) : undefined});
    assert.equal((await request('inspect', input, {Origin: 'https://evil.example'})).status, 403);
    const badHost = await new Promise((resolve, reject) => {
      http.get(app.origin + '/api/status', {headers: {Host: 'evil.example', Authorization: 'Bearer ' + token}}, response => {
        response.resume(); resolve(response.statusCode);
      }).on('error', reject);
    });
    assert.equal(badHost, 403);
    assert.equal((await request('status', null, {Authorization: ''})).status, 401);
    assert.equal((await request('install', input)).status, 409);
    assert.equal(deployed, 0);
    assert.equal((await request('inspect', input)).status, 200);
    assert.equal((await request('install', {...input, fingerprint: 'wrong'})).status, 409);
    assert.equal((await request('install', {...input, host: 'other.example', fingerprint: 'SHA256:test-only'})).status, 409);
    assert.equal((await request('install', {...input, fingerprint: 'SHA256:test-only'})).status, 202);
    assert.equal((await request('install', {...input, fingerprint: 'SHA256:test-only'})).status, 409);
    assert.equal(deployed, 1);
    assert.ok(!JSON.stringify(app.status(s.id)).includes('test-only-secret'));
    release();
    for (let i = 0; i < 50 && app.status(s.id).stage !== 'done'; i++) await new Promise(r => setTimeout(r, 20));
    assert.equal(app.status(s.id).stage, 'done');
    const result = await (await request('result')).json();
    assert.equal(result.uri, uri); assert.match(result.qr, /^data:image\/png;base64,iVBOR/);
    const connection = app.connection(s.id);
    assert.equal(JSON.parse(connection.content[0].text).uri, result.uri);
    assert.equal(connection.content[1].type, 'image');
    assert.equal(connection.content[1].data, result.qr.split(',')[1]);
    assert.ok(!JSON.stringify(connection).includes('test-only-secret'));
    assert.equal(JSON.parse(result.mihomo).proxies[0].fingerprint, 'ab'.repeat(32));
    assert.ok(!JSON.stringify(result).includes('test-only-secret'));
  } finally { release(); await app.close(); }
});

test('input rejects shell fragments, malformed hosts and mixed auth', () => {
  for (const host of ['', 'x;id', 'https://host', 'host:22', '-host', 'a\nb'])
    assert.throws(() => validateInput({...input, host}));
  assert.throws(() => validateInput({...input, privateKey: 'also-a-key'}));
  assert.throws(() => validateInput({...input, username: 'root;id'}));
  assert.throws(() => validateInput({...input, vpnPort: 22}));
  assert.equal(validateInput({...input, host: '[::1]'}).host, '::1');
});

test('Mihomo export preserves password/IPv6/pinning and never opens LAN listener', () => {
  const profile = JSON.parse(mihomoProfile(uri.replace('127.0.0.1', '[2001:db8::1]')));
  assert.equal(profile.proxies[0].password, 'test-only:@/');
  assert.equal(profile.proxies[0].server, '2001:db8::1');
  assert.equal(profile['allow-lan'], false);
  assert.throws(() => mihomoProfile(uri.replace('ab'.repeat(32), '')));
});

test('temporary credential directory has private permissions', async () => {
  const dir = await privateDirectory();
  try {
    if (process.platform === 'win32') {
      const command = '$a=[System.IO.Directory]::GetAccessControl($args[0]); [pscustomobject]@{protected=$a.AreAccessRulesProtected;rules=@($a.Access|ForEach-Object {$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value})}|ConvertTo-Json -Compress';
      // Pass path through an environment value, never interpolate it into executable PowerShell text.
      const result = JSON.parse(execFileSync('powershell.exe', ['-NoProfile', '-Command', command.replace('$args[0]', '$env:HY2_TEST_DIRECTORY')], {encoding: 'utf8', windowsHide: true, env: {...process.env, HY2_TEST_DIRECTORY: dir}}));
      assert.equal(result.protected, true);
      assert.equal(result.rules.length, 2); assert.ok(result.rules.includes('S-1-5-18'));
    } else assert.equal((await stat(dir)).mode & 0o777, 0o700);
  } finally { await rm(dir, {recursive: true}); }
});

test('download fallback only on transport failure; mismatched binary never accepted', async t => {
  const bytes = Buffer.from('test-only-binary'); const hash = createHash('sha256').update(bytes).digest('hex');
  const visited = [];
  t.mock.method(globalThis, 'fetch', async url => { visited.push(url); if (url.includes('primary')) throw new Error('offline'); return new Response(bytes); });
  assert.deepEqual(await downloadVerified(['https://primary.test/a', 'https://backup.test/a'], hash), bytes);
  assert.equal(visited.length, 2);
  await assert.rejects(downloadVerified(['https://backup.test/a'], '0'.repeat(64)), /校验失败/);
});
