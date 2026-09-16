const $ = id => document.getElementById(id);
const token = location.hash.slice(1);
history.replaceState(null, '', '/'); // Keep the capability out of browser history after opening.
let fingerprint, result, pending, timer;
const headers = {Authorization: 'Bearer ' + token, 'Content-Type': 'application/json'};
async function api(path, value) {
  const response = await fetch('/api/' + path, {method: value ? 'POST' : 'GET', headers, body: value ? JSON.stringify(value) : undefined, cache: 'no-store'});
  const data = await response.json(); if (!response.ok) throw new Error(data.error); return data;
}
function error(e) { $('error').textContent = e.message; $('error').hidden = false; }
function stage(step) { document.querySelectorAll('.steps li').forEach((li, i) => li.classList.toggle('current', i === step)); }
function render(s) {
  if (['checking', 'installing', 'verifying'].includes(s.stage)) {
    $('setup').hidden = true; $('progress').hidden = false; $('progress-text').textContent = s.message; stage(1);
  }
  if (s.stage === 'error') { clearInterval(timer); $('progress').hidden = true; $('setup').hidden = false; $('form').hidden = false; $('trust').hidden = true; error(new Error(s.message)); }
  if (s.stage === 'done') { clearInterval(timer); showResult().catch(error); }
}
async function poll() { try { render(await api('status')); } catch (e) { clearInterval(timer); error(e); } }
async function readInput() {
  const values = Object.fromEntries(new FormData($('form')));
  if ($('method').value === 'key') {
    if (!$('key').files[0]) throw new Error('请选择私钥文件');
    if ($('key').files[0].size > 65536) throw new Error('私钥文件过大，请确认选择正确');
    values.privateKey = await $('key').files[0].text(); delete values.password;
  } else delete values.passphrase;
  return values;
}
$('method').addEventListener('change', () => { $('key-fields').hidden = $('method').value !== 'key'; $('password-label').hidden = $('method').value === 'key'; });
$('form').addEventListener('submit', async event => {
  event.preventDefault(); $('inspect').disabled = true; $('error').hidden = true;
  try {
    pending = await readInput(); const s = await api('inspect', pending); fingerprint = s.fingerprint;
    $('fingerprint').textContent = fingerprint; $('form').hidden = true; $('trust').hidden = false;
  } catch (e) { pending = undefined; error(e); } finally { $('inspect').disabled = false; }
});
$('back').addEventListener('click', () => { pending = undefined; $('trust').hidden = true; $('form').hidden = false; });
$('install').addEventListener('click', async () => {
  $('install').disabled = true; $('error').hidden = true;
  try {
    const s = await api('install', {...pending, fingerprint}); pending = undefined;
    $('form').elements.password.value = ''; $('form').elements.passphrase.value = ''; $('key').value = '';
    render(s); timer = setInterval(poll, 2500);
  } catch (e) { error(e); } finally { $('install').disabled = false; }
});
async function showResult() {
  result = await api('result'); $('setup').hidden = true; $('progress').hidden = true; $('result').hidden = false; stage(2);
  document.querySelector('h1').textContent = '最后一步，连接。';
  document.querySelector('.intro > p:last-child').textContent = '打开客户端，扫码或粘贴链接，就可以尝试连接了。';
  $('result-message').textContent = result.message;
  $('verified-label').textContent = result.verified ? '连接检测通过' : '服务已安装 · 请尝试连接';
  $('qr').src = result.qr; $('uri').value = result.uri; $('downloads').replaceChildren();
  for (const item of result.downloads.filter(d => d.id !== 'other')) {
    const card = document.createElement('div'); card.className = 'download';
    const heading = document.createElement('strong'); heading.textContent = item.name; card.append(heading);
    const p = document.createElement('p'); p.textContent = item.instruction; card.append(p);
    for (const [label, url] of [['GitHub 官方下载 ↗', item.url], ['备用下载 ↗', item.backup]]) {
      if (!url) continue;
      const a = document.createElement('a'); a.textContent = label; a.href = url; a.target = '_blank'; a.rel = 'noreferrer'; card.append(a, document.createTextNode('　'));
    }
    const detail = document.createElement('details');
    const summary = document.createElement('summary'); summary.textContent = '版本与校验值'; detail.append(summary);
    const hash = document.createElement('small'); hash.textContent = '版本 ' + item.version + ' · SHA256: ' + item.sha256; detail.append(hash); card.append(detail);
    $('downloads').append(card);
  }
}
$('copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(result.uri); $('copy').textContent = '已复制，去客户端粘贴'; }
  catch { $('uri').focus(); $('uri').select(); error(new Error('浏览器未允许自动复制，链接已选中，请手动复制')); }
});
$('mihomo').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([result.mihomo], {type: 'application/yaml'}));
  const link = document.createElement('a'); link.href = url; link.download = 'hy2-easy-mihomo.yaml'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
});
if (!/^[a-f0-9]{64}$/.test(token)) { $('setup').hidden = true; error(new Error('请使用 Agent 给出的完整配置链接打开此页面')); }
else poll().then(() => { if (!$('progress').hidden && !timer) timer = setInterval(poll, 2500); });
