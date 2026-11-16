import { describe, it, expect, vi } from 'vitest'
import { availablePort, buildQuickPlan, hostOnly, writeQuickPlan, certificateDomain } from './quickNode'
import type { QuickOptions, QuickWriter } from './quickNode'

const base: QuickOptions = { protocol: 'socks', host: '192.0.2.1', port: 1080, tag: 'quick-test' }

describe('quick node configuration and exported credentials', () => {
  it('restricts automatic certificate names to exact DNS names without paths', () => {
    for (const domain of ['../secret', '127.0.0.1', '::1', '*.example.com', 'localhost', 'a.example.com/path', '-a.example.com']) expect(() => certificateDomain(domain)).toThrow()
    expect(certificateDomain('Proxy.Example.com')).toBe('proxy.example.com')
  })
  it('uses built-in ACME with HTTP validation and no DNS API secret', () => {
    const p = buildQuickPlan({ ...base, protocol: 'hysteria2', acme: { domain: 'proxy.example.com', email: 'operator@example.com' } })
    expect(p.tls).toMatchObject({ server: { certificate_provider: {
      type: 'acme', domain: ['proxy.example.com'], disable_http_challenge: false, disable_tls_alpn_challenge: true,
      data_directory: './certificates/proxy.example.com',
    } }, client: { insecure: false } })
    expect(p.link).not.toMatch(/insecure|operator@|certificates/)
    expect(() => buildQuickPlan({ ...base, protocol: 'hysteria2', acme: { domain: 'proxy.example.com', email: 'bad\nmail' } })).toThrow()
  })
  it('rejects addresses with paths, credentials, ports or whitespace', () => {
    for (const value of ['https://example.com', 'a@b.com', 'example.com:443', 'example.com/path', 'a b', '']) {
      expect(() => hostOnly(value)).toThrow()
    }
    expect(hostOnly('[2001:db8::1]')).toBe('2001:db8::1')
  })
  it('never builds an enabled or unauthenticated SOCKS listener', () => {
    const p = buildQuickPlan(base)
    expect(p.inbound).toMatchObject({ enable: false, listen: '127.0.0.1', type: 'socks' })
    expect(p.client.config).toEqual({ socks: { username: p.username, password: p.password } })
    expect(p.password).toHaveLength(48)
    expect(p.link).toContain(btoa(`${p.username}:${p.password}`))
    expect(p.link).toContain('@127.0.0.1:1080')
  })
  it('requires an explicit external SOCKS choice and brackets IPv6 links', () => {
    const p = buildQuickPlan({ ...base, host: '2001:db8::1', socksPublic: true })
    expect(p.inbound.listen).toBe('::')
    expect(p.link).toContain('@[2001:db8::1]:1080')
  })
  it('keeps Hysteria2 verification on, selects BBR, and adds no bandwidth cap', () => {
    const p = buildQuickPlan({ ...base, protocol: 'hysteria2', tlsId: 2, serverName: 'proxy.example.com' })
    expect(p.inbound.ignore_client_bandwidth).toBe(true)
    expect(p.inbound).not.toHaveProperty('up_mbps')
    expect(p.inbound).not.toHaveProperty('down_mbps')
    expect(p.link).not.toMatch(/insecure|allowInsecure/)
    expect(p.link).toContain('sni=proxy.example.com')
    expect(() => buildQuickPlan({ ...base, protocol: 'hysteria2' })).toThrow()
  })
  it('keeps the Reality private key out of the client link and matches identifiers', () => {
    const p = buildQuickPlan({ ...base, protocol: 'reality', target: 'target.example.com', privateKey: 'A'.repeat(43), publicKey: 'B'.repeat(43) })
    const url = new URL(p.link)
    const tls = p.tls as { server: { reality: { short_id: string[] } }, client: { insecure: boolean } }
    expect(p.link).not.toContain('A'.repeat(43))
    expect(url.searchParams.get('pbk')).toBe('B'.repeat(43))
    expect(url.searchParams.get('sid')).toBe(tls.server.reality.short_id[0])
    expect(url.username).toBe(p.password)
    expect(p.password).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(tls.client.insecure).toBe(false)
    expect(url.searchParams.get('flow')).toBe('xtls-rprx-vision')
  })
  it('does not reuse secrets across nodes', () => {
    const a = buildQuickPlan(base), b = buildQuickPlan(base)
    expect(a.password).not.toBe(b.password)
    expect(a.username).not.toBe(b.username)
  })
  it('validates ports and avoids occupied ports without infinite retries', () => {
    expect(availablePort(443, [443, 20000])).toBe(20001)
    for (const port of [0, 65536, 1.5, NaN]) expect(() => buildQuickPlan({ ...base, port })).toThrow()
  })
})

function writer(): QuickWriter {
  return {
    saveTls: vi.fn().mockResolvedValue(10), saveClient: vi.fn().mockResolvedValue(20),
    saveInbound: vi.fn().mockResolvedValue(30), verifyClient: vi.fn().mockResolvedValue(true),
    enableInbound: vi.fn().mockResolvedValue(undefined),
  }
}
describe('staged activation', () => {
  it('creates a disabled inbound with an authenticated user, verifies binding, then enables', async () => {
    const w = writer(), p = buildQuickPlan(base)
    await writeQuickPlan(p, w)
    expect(w.saveInbound).toHaveBeenCalledWith(expect.objectContaining({ enable: false }), 20)
    expect(w.verifyClient).toHaveBeenCalledWith(20, 30)
    expect(w.enableInbound).toHaveBeenCalledWith(expect.objectContaining({ id: 30, enable: true }))
    expect(p.inbound.enable).toBe(false)
    const order = [w.saveClient, w.saveInbound, w.verifyClient, w.enableInbound].map(f => vi.mocked(f).mock.invocationCallOrder[0])
    expect(order).toEqual([...order].sort((a, b) => a - b))
  })
  it.each(['saveClient', 'saveInbound', 'verifyClient'] as const)('never enables after %s failure', async stage => {
    const w = writer()
    vi.mocked(w[stage]).mockRejectedValue(new Error('simulated timeout'))
    await expect(writeQuickPlan(buildQuickPlan(base), w)).rejects.toThrow()
    expect(w.enableInbound).not.toHaveBeenCalled()
    expect(w[stage]).toHaveBeenCalledTimes(1)
  })
  it('does not enable if the server reports a missing binding or invalid ID', async () => {
    const w = writer()
    vi.mocked(w.verifyClient).mockResolvedValue(false)
    await expect(writeQuickPlan(buildQuickPlan(base), w)).rejects.toThrow()
    expect(w.enableInbound).not.toHaveBeenCalled()
    vi.mocked(w.saveClient).mockResolvedValue(0)
    await expect(writeQuickPlan(buildQuickPlan(base), w)).rejects.toThrow()
  })
  it('stops before creating a client if Reality TLS fails', async () => {
    const w = writer()
    vi.mocked(w.saveTls).mockRejectedValue(new Error('TLS save failed'))
    const p = buildQuickPlan({ ...base, protocol: 'reality', target: 'target.example.com', privateKey: 'A'.repeat(43), publicKey: 'B'.repeat(43) })
    await expect(writeQuickPlan(p, w)).rejects.toThrow()
    expect(w.saveClient).not.toHaveBeenCalled()
  })
})
