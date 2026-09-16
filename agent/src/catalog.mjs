// Original upstream binaries only. A backup is advertised only after publication and verification.
export const downloads = [
  {id: 'windows', name: 'v2rayN · Windows 64 位', version: '7.24.9',
    url: 'https://github.com/2dust/v2rayN/releases/download/7.24.9/v2rayN-windows-64.zip',
    sha256: '84a3b7d249db0c87951566f3fa4af520d97115469a404e1d3d506096f6186685',
    source: 'https://github.com/2dust/v2rayN/tree/7.24.9', license: 'GPL-3.0', backup: null,
    instruction: '下载并解压 → 打开 v2rayN.exe → 复制连接链接 → 在 v2rayN 按 Ctrl+V → 选中线路并开启系统代理。'},
  {id: 'android', name: 'v2rayNG · 安卓（常见 64 位手机）', version: '2.2.6',
    url: 'https://github.com/2dust/v2rayNG/releases/download/2.2.6/v2rayNG_2.2.6_arm64-v8a.apk',
    sha256: '62b0675c0986a8613f1bb67f1a68c366c6357e04a68687a3bd907170594c437d',
    source: 'https://github.com/2dust/v2rayNG/tree/2.2.6', license: 'GPL-3.0', backup: null,
    instruction: '下载并安装 → 点右上角 + → 扫码或从剪贴板导入 → 点右下角连接按钮。'},
  {id: 'other', name: '苹果 / Mac / Mihomo（Clash.Meta）等其他客户端',
    url: 'https://v2.hysteria.network/docs/getting-started/3rd-party-apps/',
    instruction: '选择支持 Hysteria 2 和证书指纹的客户端。Mihomo 可在配置页下载专用配置；苹果端尚未真机验证。'}
];

export function mihomoProfile(uri) {
  const u = new URL(uri);
  const pin = u.searchParams.get('pinSHA256');
  if (u.protocol !== 'hysteria2:' || !/^[a-f0-9]{64}$/i.test(pin || '') || !u.username || !u.port)
    throw new Error('连接信息缺少有效的证书指纹');
  // JSON is valid YAML, avoiding hand-built YAML escaping for passwords and IPv6.
  return JSON.stringify({
    'mixed-port': 7890, 'allow-lan': false, mode: 'rule', 'log-level': 'warning',
    proxies: [{name: 'hy2-easy', type: 'hysteria2', server: u.hostname.replace(/^\[|\]$/g, ''),
      port: Number(u.port), password: decodeURIComponent(u.username), sni: u.searchParams.get('sni'),
      'skip-cert-verify': true, fingerprint: pin}],
    'proxy-groups': [{name: '连接', type: 'select', proxies: ['hy2-easy', 'DIRECT']}],
    rules: ['IP-CIDR,127.0.0.0/8,DIRECT,no-resolve', 'IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
      'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve', 'IP-CIDR,192.168.0.0/16,DIRECT,no-resolve',
      'IP-CIDR6,::1/128,DIRECT,no-resolve', 'IP-CIDR6,fc00::/7,DIRECT,no-resolve', 'MATCH,连接']
  }, null, 2);
}
