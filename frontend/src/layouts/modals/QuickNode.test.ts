import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QuickNode from './QuickNode.vue'
import Data from '@/store/modules/data'
import HttpUtils from '@/plugins/httputil'

vi.mock('@/plugins/httputil', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('notivue', () => ({ push: { error: vi.fn(), success: vi.fn() } }))

type Row = Record<string, any>
type Form = {
  protocol: 'socks' | 'reality' | 'hysteria2'; host: string; tag: string; port: number;
  tlsId: number; target: string; started: boolean; error: string;
  certificateMode: 'existing' | 'acme'; certificateHost: string; certificateEmail: string; certificateReady: boolean;
  result?: { link: string }; create(): Promise<void>;
}
let db: Record<string, any>, calls: Row[], sequence: number
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  calls = []; sequence = 10
  db = { config: {}, inbounds: [], endpoints: [], clients: [], outbounds: [], tls: [{ id: 1, name: 'Test TLS', server: { enabled: true, server_name: 'proxy.example.com', certificate_path: '/test/cert.pem', alpn: ['h3'] }, client: { insecure: false } }] }
  vi.mocked(HttpUtils.get).mockImplementation(async (url, data: Row = {}) => {
    let obj: unknown = db
    if (url.endsWith('keypairs')) obj = ['PrivateKey: ' + 'A'.repeat(43), 'PublicKey: ' + 'B'.repeat(43)]
    if (url.endsWith('status')) obj = { sbd: { running: db.coreRunning !== false } }
    if (url.endsWith('clients')) obj = { clients: db.clients.filter((c: Row) => c.id === data.id) }
    return { success: true, msg: '', obj: structuredClone(obj) } as any
  })
  vi.mocked(HttpUtils.post).mockImplementation(async (_url, request: Row | null) => {
    const data = request!
    const value = JSON.parse(data.data)
    calls.push(structuredClone({ object: data.object, action: data.action, value }))
    if (data.action === 'new') {
      value.id = ++sequence
      db[data.object].push(value)
      if (data.object === 'inbounds') db.clients.find((c: Row) => c.id === Number(data.initUsers)).inbounds.push(value.id)
    } else {
      db[data.object][db[data.object].findIndex((c: Row) => c.id === value.id)] = value
    }
    return { success: true, msg: '', obj: structuredClone(db) } as any
  })
})

function mountForm() {
  const wrapper = shallowMount(QuickNode, { props: { visible: false }, global: {
    stubs: Object.fromEntries(['VDialog', 'VCard', 'VCardText', 'VSelect', 'VTextField', 'VAlert', 'VSwitch', 'VCheckbox', 'VTextarea', 'VBtn', 'VCardActions', 'VSpacer'].map(name => [name, true])),
  } })
  const vm = wrapper.vm as unknown as Form
  vm.host = '192.0.2.1'; vm.tag = 'quick-test'; vm.port = 20443
  vm.certificateMode = 'existing'
  return { wrapper, vm }
}

describe('quick form with the real S-UI store and simulated HTTP responses', () => {
  it('refuses to write when the real core status is down', async () => {
    const { wrapper, vm } = mountForm()
    db.coreRunning = false; vm.protocol = 'socks'
    await vm.create()
    expect(vm.error).toContain('核心未运行')
    expect(calls).toHaveLength(0)
    wrapper.unmount()
  })
  it('creates fresh ACME TLS without replacing the global config or relaxing verification', async () => {
    const { wrapper, vm } = mountForm()
    vm.protocol = 'hysteria2'; vm.certificateMode = 'acme'
    vm.certificateHost = 'proxy.example.com'; vm.certificateEmail = 'operator@example.com'; vm.certificateReady = true
    await vm.create()
    expect(vm.error).toBe('')
    expect(calls[0].object).toBe('tls')
    expect(calls[0].value.server.certificate_provider).toMatchObject({ type: 'acme', disable_tls_alpn_challenge: true })
    expect(calls.some(c => c.object === 'config')).toBe(false)
    expect(vm.result?.link).not.toMatch(/insecure/i)
    wrapper.unmount()
  })
  it('requires ACME prerequisites before writing anything', async () => {
    const { wrapper, vm } = mountForm()
    vm.protocol = 'hysteria2'; vm.certificateMode = 'acme'
    await vm.create()
    expect(vm.error).toContain('TCP 80')
    expect(calls).toHaveLength(0)
    wrapper.unmount()
  })
  it.each(['hysteria2', 'reality', 'socks'] as const)('saves and exports %s using S-UI field shapes', async protocol => {
    const { wrapper, vm } = mountForm()
    vm.protocol = protocol; vm.tlsId = 1; vm.target = 'target.example.com'
    await vm.create()
    expect(vm.error).toBe('')
    expect(vm.result?.link).toMatch(new RegExp(`^${protocol === 'reality' ? 'vless' : protocol}://`))
    expect(db.inbounds).toHaveLength(1)
    expect(db.inbounds[0].enable).toBe(true)
    expect(db.clients[0].inbounds).toEqual([db.inbounds[0].id])
    const creation = calls.find(c => c.object === 'inbounds' && c.action === 'new')!
    expect(creation.value.enable).toBe(false)
    expect(calls.at(-1)?.value.enable).toBe(true)
    const count = calls.length
    await vm.create()
    expect(calls).toHaveLength(count)
    wrapper.unmount()
  })
  it('rejects an insecure TLS selection before any writes', async () => {
    const { wrapper, vm } = mountForm()
    db.tls[0].client.insecure = true
    vm.protocol = 'hysteria2'; vm.tlsId = 1
    await vm.create()
    expect(vm.error).toContain('证书验证')
    expect(calls).toHaveLength(0)
    wrapper.unmount()
  })
  it('refreshes occupied ports instead of trusting stale frontend state', async () => {
    const { wrapper, vm } = mountForm()
    vm.protocol = 'socks'
    db.inbounds.push({ id: 5, tag: 'existing', listen_port: 20443 })
    expect(Data().inbounds).toHaveLength(0)
    await vm.create()
    expect(vm.error).toContain('端口已')
    expect(calls).toHaveLength(0)
    wrapper.unmount()
  })
  it('reports partial saves and prevents duplicate retries after an unknown write result', async () => {
    const { wrapper, vm } = mountForm()
    vm.protocol = 'socks'
    vi.mocked(HttpUtils.post).mockResolvedValueOnce({ success: false, msg: 'timeout', obj: null })
    await vm.create()
    expect(vm.error).toContain('可能已保存部分对象')
    expect(vm.started).toBe(true)
    await vm.create()
    expect(HttpUtils.post).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
