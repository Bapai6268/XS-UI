// Browser smoke test with a simulated S-UI API. Does not contact any VPS.
const { chromium } = require(require.resolve('playwright', { paths: [process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES || process.cwd()] }))
const assert = require('node:assert/strict')
;(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium' })
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('s-ui-auth', '1'); localStorage.setItem('locale', 'zhHans') })
  let seq = 10
  const db = { config: {}, inbounds: [], endpoints: [], clients: [], outbounds: [], services: [], onlines: {}, maintenance: false, tls: [{ id: 1, name: '测试证书', server: { enabled: true, server_name: 'proxy.example.com', certificate_path: '/test/cert.pem', key_path: '/test/key.pem', alpn: ['h3'] }, client: { enabled: true, insecure: false } }] }
  const writes = []
  await page.route('**/api/**', async route => {
    const req = route.request(), url = new URL(req.url()), endpoint = url.pathname.split('/').pop()
    let obj = {}, success = true
    if (endpoint === 'load') obj = db
    else if (endpoint === 'status') obj = { sbd: { running: true } }
    else if (endpoint === 'checkUpdate') obj = { hasUpdate: false }
    else if (endpoint === 'keypairs') obj = ['PrivateKey: ' + 'A'.repeat(43), 'PublicKey: ' + 'B'.repeat(43)]
    else if (endpoint === 'clients') obj = { clients: db.clients.filter(c => c.id === Number(url.searchParams.get('id'))) }
    else if (endpoint === 'save') {
      const form = new URLSearchParams(req.postData()), object = form.get('object'), action = form.get('action')
      const value = JSON.parse(form.get('data'))
      writes.push({ object, action, value: structuredClone(value) })
      if (action === 'new') {
        value.id = ++seq
        db[object].push(value)
        if (object === 'inbounds') {
          assert.equal(value.enable, false)
          const client = db.clients.find(c => c.id === Number(form.get('initUsers')))
          assert.ok(client)
          client.inbounds.push(value.id)
        }
      } else {
        assert.equal(object, 'inbounds')
        assert.ok(db.clients.some(c => c.inbounds.includes(value.id)))
        db[object][db[object].findIndex(i => i.id === value.id)] = value
      }
      obj = db
    }
    await route.fulfill({ json: { success, msg: '', obj } })
  })
  await page.goto('http://127.0.0.1:3000/app/inbounds')
  for (const protocol of ['Hysteria2', 'VLESS + Reality + Vision', 'SOCKS5']) {
    await page.getByRole('button', { name: '快捷创建节点', exact: true }).click()
    if (protocol !== 'Hysteria2') {
      await page.getByRole('combobox', { name: '协议', exact: true }).click()
      await page.getByRole('option', { name: protocol, exact: true }).click()
    }
    await page.getByRole('textbox', { name: '新 VPS 的公网 IP 或直连域名' }).fill('192.0.2.10')
    if (protocol === 'Hysteria2') {
      await page.getByRole('combobox', { name: '证书方式', exact: true }).click()
      await page.getByRole('option', { name: '使用已有证书', exact: true }).click()
      await page.getByRole('combobox', { name: '已有的有效 TLS 证书' }).click()
      await page.getByRole('option', { name: /测试证书/ }).click()
    }
    if (protocol.includes('Reality')) await page.getByRole('textbox', { name: 'Reality 目标域名' }).fill('target.example.com')
    await page.getByRole('button', { name: '生成并启用', exact: true }).click()
    const field = page.getByRole('textbox', { name: '节点链接（含凭据，请妥善保存）' })
    await field.waitFor({ timeout: 15000 })
    const link = await field.inputValue()
    assert.ok(link.startsWith(protocol === 'Hysteria2' ? 'hysteria2://' : protocol === 'SOCKS5' ? 'socks://' : 'vless://'))
    assert.ok(!link.includes('insecure=1'))
    await page.getByRole('button', { name: '关闭', exact: true }).click()
  }
  assert.equal(db.inbounds.length, 3)
  assert.ok(db.inbounds.every(i => i.enable))
  assert.equal(db.clients.length, 3)
  assert.equal(errors.length, 0, errors.join('\n'))
  // Inspect the form without any secret values in the screenshot.
  await page.getByRole('button', { name: '快捷创建节点', exact: true }).click()
  if (process.env.QUICK_NODE_SCREENSHOT) await page.screenshot({ path: process.env.QUICK_NODE_SCREENSHOT, fullPage: true })
  console.log(JSON.stringify({ protocols: 3, apiWrites: writes.length, runtimeErrors: errors.length, result: 'PASS (simulated API; no live proxy connectivity tested)' }))
  await browser.close()
})().catch(error => { console.error(error.message); process.exit(1) })
