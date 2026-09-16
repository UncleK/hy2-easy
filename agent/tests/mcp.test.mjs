import test from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';

test('real stdio MCP discovery and local setup work without leaking stderr into protocol', async () => {
  const client = new Client({name: 'hy2-test', version: '1.0.0'});
  const transport = new StdioClientTransport({command: process.execPath, args: [fileURLToPath(new URL('../src/mcp.mjs', import.meta.url))], stderr: 'pipe'});
  try {
    await client.connect(transport);
    const {tools} = await client.listTools();
    assert.deepEqual(tools.map(t => t.name).sort(), ['hy2_connection', 'hy2_downloads', 'hy2_setup', 'hy2_status']);
    const result = await client.callTool({name: 'hy2_setup', arguments: {}});
    const session = JSON.parse(result.content[0].text);
    assert.match(session.url, /^http:\/\/127\.0\.0\.1:\d+\/#/);
    const page = await fetch(session.url);
    assert.equal(page.status, 200); assert.match(page.headers.get('content-security-policy'), /frame-ancestors 'none'/);
    assert.ok((await page.text()).includes('服务器密码'));
    const status = await client.callTool({name: 'hy2_status', arguments: {id: session.id}});
    assert.equal(JSON.parse(status.content[0].text).stage, 'ready');
    const resultBeforeInstall = await client.callTool({name: 'hy2_connection', arguments: {id: session.id}});
    assert.equal(resultBeforeInstall.isError, true);
  } finally { await client.close(); }
});
