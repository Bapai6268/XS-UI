// Quick-create plans contain secrets only in memory. Never log or persist them
// in browser storage. Saving is delegated to S-UI's authenticated session API.
export type QuickProtocol = 'hysteria2' | 'reality' | 'socks'
export interface QuickOptions {
  protocol: QuickProtocol
  host: string
  port: number
  tag: string
  tlsId?: number
  serverName?: string
  target?: string
  publicKey?: string
  privateKey?: string
  socksPublic?: boolean
  acme?: { domain: string; email: string }
}
export interface QuickPlan {
  inbound: Record<string, unknown>
  client: Record<string, unknown>
  tls?: Record<string, unknown>
  link: string
  username: string
  password: string
}

export function hostOnly(value: string): string {
  const host = value.trim().replace(/^\[|\]$/g, '')
  if (!host || /[\s/@?#\\]/.test(host) || host.includes('://')) throw new Error('请填写 IP 或域名，不要带端口、路径或 https://。')
  try {
    const parsed = new URL(`https://${host.includes(':') ? `[${host}]` : host}`)
    if (parsed.port || parsed.username || parsed.pathname !== '/') throw new Error()
  } catch { throw new Error('服务器地址格式不正确。') }
  return host
}

export function secretHex(bytes: number): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), b => b.toString(16).padStart(2, '0')).join('')
}

function secretUuid(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function availablePort(preferred: number, used: number[]): number {
  const occupied = new Set(used)
  if (!occupied.has(preferred)) return preferred
  for (let port = 20000; port <= 60000; port++) if (!occupied.has(port)) return port
  throw new Error('面板中没有可用的候选端口。')
}

export function buildQuickPlan(o: QuickOptions): QuickPlan {
  const host = hostOnly(o.host)
  if (!Number.isInteger(o.port) || o.port < 1 || o.port > 65535) throw new Error('端口必须在 1–65535 之间。')
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(o.tag)) throw new Error('节点名称只使用字母、数字、短横线和下划线。')
  if (!['hysteria2', 'reality', 'socks'].includes(o.protocol)) throw new Error('不支持的协议。')
  const authority = `${host.includes(':') ? `[${host}]` : host}:${o.port}`
  const name = `quick-${secretHex(8)}`
  const password = secretHex(24)
  const type = o.protocol === 'reality' ? 'vless' : o.protocol
  const inbound: Record<string, unknown> = {
    id: 0, type, tag: o.tag, enable: false, tls_id: o.tlsId ?? 0,
    listen: type === 'socks' && !o.socksPublic ? '127.0.0.1' : host.includes(':') ? '::' : '0.0.0.0',
    listen_port: o.port, addrs: [{ server: host, server_port: o.port, remark: o.tag }], out_json: {},
  }
  const client: Record<string, unknown> = {
    enable: true, name, remark: o.tag, group: 'quick-create', desc: '',
    config: {}, inbounds: [], links: [], volume: 0, expiry: 0, up: 0, down: 0,
  }
  const plan: QuickPlan = { inbound, client, link: '', username: name, password }
  const fragment = `#${encodeURIComponent(o.tag)}`
  if (o.protocol === 'hysteria2') {
    if (!o.acme && (!o.tlsId || o.tlsId < 1)) throw new Error('请选择已有证书或自动申请证书。')
    const sni = o.acme ? certificateDomain(o.acme.domain) : hostOnly(o.serverName ?? '')
    if (o.acme) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(o.acme.email) || o.acme.email.length > 254) throw new Error('请填写有效的证书联系邮箱。')
      plan.tls = {
        id: 0, name: `quick-${o.tag}-${secretHex(4)}`,
        server: { enabled: true, server_name: sni, alpn: ['h3'], min_version: '1.3',
          certificate_provider: {
            type: 'acme', domain: [sni], email: o.acme.email,
            provider: 'letsencrypt', data_directory: `./certificates/${sni}`,
            disable_http_challenge: false, disable_tls_alpn_challenge: true,
          },
        },
        client: { enabled: true, server_name: sni, alpn: ['h3'], insecure: false },
      }
    }
    inbound.ignore_client_bandwidth = true
    client.config = { hysteria2: { name, password } }
    plan.link = `hysteria2://${password}@${authority}?${new URLSearchParams({ sni, alpn: 'h3' })}${fragment}`
  } else if (o.protocol === 'reality') {
    const target = hostOnly(o.target ?? '')
    if (target.includes(':') || !target.includes('.') || /^[\d.]+$/.test(target)) throw new Error('Reality 目标请填写支持 TLS 1.3 的域名。')
    if (!/^[A-Za-z0-9_-]{43}$/.test(o.privateKey ?? '') || !/^[A-Za-z0-9_-]{43}$/.test(o.publicKey ?? '')) throw new Error('Reality 密钥生成失败。')
    const uuid = secretUuid()
    const sid = secretHex(8)
    plan.tls = {
      id: 0, name: `quick-${o.tag}-${secretHex(4)}`,
      server: { enabled: true, server_name: target, reality: {
        enabled: true, handshake: { server: target, server_port: 443 }, private_key: o.privateKey, short_id: [sid],
      } },
      client: { enabled: true, server_name: target, insecure: false,
        utls: { enabled: true, fingerprint: 'chrome' },
        reality: { enabled: true, public_key: o.publicKey, short_id: sid },
      },
    }
    client.config = { vless: { name, uuid, flow: 'xtls-rprx-vision' } }
    plan.link = `vless://${uuid}@${authority}?${new URLSearchParams({ encryption: 'none', security: 'reality', type: 'tcp', flow: 'xtls-rprx-vision', sni: target, fp: 'chrome', pbk: o.publicKey!, sid })}${fragment}`
    plan.password = uuid
  } else {
    client.config = { socks: { username: name, password } }
    const addr = o.socksPublic ? authority : `127.0.0.1:${o.port}`
    plan.link = `socks://${btoa(`${name}:${password}`)}@${addr}${fragment}`
  }
  return plan
}

// Only exact public DNS names: never a wildcard, filesystem path or local IP.
export function certificateDomain(value: string): string {
  const domain = value.trim().toLowerCase()
  if (domain.length > 253 || !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(domain)) {
    throw new Error('自动证书需要已解析到本机的完整域名，不接受 IP、通配符或路径。')
  }
  return domain
}

export interface QuickWriter {
  saveTls(value: Record<string, unknown>): Promise<number>
  saveClient(value: Record<string, unknown>): Promise<number>
  saveInbound(value: Record<string, unknown>, clientId: number): Promise<number>
  verifyClient(clientId: number, inboundId: number): Promise<boolean>
  enableInbound(value: Record<string, unknown>): Promise<void>
}

// New inbounds are staged DISABLED. Even when a request fails halfway through,
// an unauthenticated SOCKS listener is never intentionally activated. Retain
// staging objects for inspection instead of guessing whether a timed-out write
// committed and deleting data. Callers must not automatically retry writes.
export async function writeQuickPlan(plan: QuickPlan, writer: QuickWriter): Promise<void> {
  const inbound = structuredClone(plan.inbound)
  if (inbound.enable !== false) throw new Error('快捷创建必须从停用状态开始。')
  const validId = (id: number) => { if (!Number.isSafeInteger(id) || id < 1) throw new Error('服务器没有返回有效 ID。'); return id }
  if (plan.tls) inbound.tls_id = validId(await writer.saveTls(plan.tls))
  const clientId = validId(await writer.saveClient(plan.client))
  const inboundId = validId(await writer.saveInbound(inbound, clientId))
  if (!await writer.verifyClient(clientId, inboundId)) throw new Error('未确认用户已绑定节点，节点保持停用。')
  await writer.enableInbound({ ...inbound, id: inboundId, enable: true })
}
