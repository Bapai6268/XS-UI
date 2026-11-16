<template>
  <v-dialog
    :model-value="visible"
    max-width="680"
    :persistent="busy"
    @update:model-value="close"
  >
    <v-card
      title="快捷创建节点"
      :loading="busy"
    >
      <v-card-text>
        <template v-if="!result">
          <v-select
            v-model="protocol"
            label="协议"
            :items="protocols"
            :disabled="started"
            @update:model-value="resetPort"
          />
          <v-text-field
            v-model="host"
            label="新 VPS 的公网 IP 或直连域名"
            hint="不要填写经过 CDN 的面板地址。"
            persistent-hint
            :disabled="started"
          />
          <v-text-field
            v-model="tag"
            label="节点名称"
            :disabled="started"
          />
          <v-text-field
            v-model.number="port"
            type="number"
            label="端口（已自动避开面板中记录的端口）"
            :disabled="started"
          />
          <template v-if="protocol === 'hysteria2'">
            <v-select
              v-model="certificateMode"
              label="证书方式"
              :items="[{ title: '自动申请并续期（新 VPS）', value: 'acme' }, { title: '使用已有证书', value: 'existing' }]"
              :disabled="started"
            />
            <template v-if="certificateMode === 'acme'">
              <v-text-field
                v-model="certificateHost"
                label="证书域名"
                :disabled="started"
              />
              <v-text-field
                v-model="certificateEmail"
                label="证书联系邮箱"
                :disabled="started"
              />
              <v-checkbox
                v-model="certificateReady"
                label="域名已直连解析到这台 VPS，TCP 80 已放行且空闲，并同意 Let's Encrypt 服务条款"
                :disabled="started"
              />
              <a
                href="https://letsencrypt.org/repository/"
                target="_blank"
                rel="noopener noreferrer"
              >查看证书服务条款</a>
            </template>
            <v-select
              v-else
              v-model="tlsId"
              label="已有的有效 TLS 证书"
              :items="tlsItems"
              :disabled="started"
            />
            <v-alert
              type="info"
              variant="tonal"
              class="mb-3"
            >
              自动模式由代理核心申请及续期证书，TCP 80 需持续可达以供续期。
              不跳过证书验证；Hysteria2 使用内部 BBR，自适应带宽，不另加限速。
            </v-alert>
          </template>
          <template v-if="protocol === 'reality'">
            <v-text-field
              v-model="target"
              label="Reality 目标域名"
              hint="需要 VPS 能访问、支持 TLS 1.3 的目标；请先确认目标适用。密钥和 UUID 自动生成。"
              persistent-hint
              :disabled="started"
            />
          </template>
          <template v-if="protocol === 'socks'">
            <v-switch
              v-model="socksPublic"
              label="允许从服务器外部连接 SOCKS5"
              color="primary"
              :disabled="started"
            />
            <v-alert
              type="info"
              variant="tonal"
              class="mb-3"
            >
              默认只监听 VPS 本机，不能直接填进你电脑的指纹浏览器；可通过 SSH 隧道使用。
              开启外部连接后会对外监听，仍使用自动生成的用户名和密码。
            </v-alert>
            <v-checkbox
              v-if="socksPublic"
              v-model="socksAcknowledged"
              label="我会限制防火墙访问来源，并了解普通 SOCKS5 不加密连接"
              :disabled="started"
            />
          </template>
          <v-alert
            type="info"
            variant="tonal"
            class="mt-3"
          >
            创建会写入面板并尝试启用节点。请先用面板备份功能保存一份配置；防火墙和供应商安全组仍需放行所用端口。
          </v-alert>
          <v-alert
            v-if="error"
            type="error"
            variant="tonal"
            class="mt-3"
          >
            {{ error }}
          </v-alert>
        </template>
        <template v-else>
          <v-alert
            type="info"
            variant="tonal"
            class="mb-4"
          >
            节点已保存并提交启用。请导入客户端测试连接，确认核心运行和端口放行。
            <template v-if="protocol === 'hysteria2' && certificateMode === 'acme'">
              首次证书在后台申请，保存成功不代表证书已签发。签发完成前连接会失败；请在核心日志查看结果，勿关闭客户端的证书验证。
            </template>
          </v-alert>
          <v-textarea
            :model-value="result.link"
            label="节点链接（含凭据，请妥善保存）"
            readonly
            auto-grow
          />
          <v-btn
            variant="tonal"
            @click="copy"
          >
            {{ copied ? '已复制' : '复制节点链接' }}
          </v-btn>
          <template v-if="protocol === 'socks'">
            <v-text-field
              :model-value="result.username"
              label="SOCKS5 用户名"
              readonly
            />
            <v-text-field
              :model-value="result.password"
              label="SOCKS5 密码"
              readonly
            />
          </template>
          <p class="mt-4">
            后续可在原来的入站、客户端和 TLS 页面管理。节点分享链接不会自动修改路由器配置。
          </p>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          :disabled="busy"
          @click="close"
        >
          关闭
        </v-btn>
        <v-btn
          v-if="!result"
          color="primary"
          variant="tonal"
          :disabled="started || (socksPublic && protocol === 'socks' && !socksAcknowledged)"
          :loading="busy"
          @click="create"
        >
          生成并启用
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Data from '@/store/modules/data'
import HttpUtils from '@/plugins/httputil'
import { availablePort, buildQuickPlan, hostOnly, secretHex, writeQuickPlan } from '@/plugins/quickNode'
import type { QuickPlan, QuickProtocol, QuickOptions } from '@/plugins/quickNode'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()
const store = Data()
const protocol = ref<QuickProtocol>('hysteria2')
const protocols = [{ title: 'Hysteria2', value: 'hysteria2' }, { title: 'VLESS + Reality + Vision', value: 'reality' }, { title: 'SOCKS5', value: 'socks' }]
const host = ref('')
const tag = ref('')
const port = ref(443)
const tlsId = ref<number>()
const certificateMode = ref<'acme' | 'existing'>('acme')
const certificateHost = ref('')
const certificateEmail = ref('')
const certificateReady = ref(false)
const target = ref('')
const socksPublic = ref(false)
const socksAcknowledged = ref(false)
const busy = ref(false)
const started = ref(false)
const error = ref('')
const result = ref<QuickPlan>()
const copied = ref(false)
// Conservative port selection also avoids disabled records and endpoints.
const usedPorts = () => [...store.inbounds, ...store.endpoints].map(i => i.listen_port).filter(Number.isFinite)
const tlsItems = computed(() => store.tlsConfigs.filter(t =>
  t.server.enabled && !t.server.reality?.enabled && !t.client.insecure && t.server.server_name &&
  (t.server.certificate_path || t.server.certificate?.length || t.server.certificate_provider) &&
  (!t.server.alpn?.length || t.server.alpn.includes('h3'))
).map(t => ({ title: `${t.name} (${t.server.server_name})`, value: t.id })))

function resetPort() {
  error.value = ''
  try { port.value = availablePort(protocol.value === 'socks' ? 1080 : 443, usedPorts()) }
  catch (e) { error.value = String(e) }
  tag.value = `${protocol.value}-${secretHex(4)}`
}
watch(() => props.visible, open => {
  if (!open) return
  result.value = undefined
  started.value = false
  error.value = ''
  copied.value = false
  resetPort()
})
function close() {
  if (busy.value) return
  result.value = undefined
  emit('close')
}
async function copy() {
  if (!result.value) return
  try { await navigator.clipboard.writeText(result.value.link); copied.value = true }
  catch { copied.value = false }
}
async function create() {
  if (busy.value || started.value) return
  error.value = ''
  busy.value = true
  let wrote = false
  try {
    if (protocol.value === 'socks' && socksPublic.value && !socksAcknowledged.value) throw new Error('请确认 SOCKS5 的访问范围。')
    hostOnly(host.value)
    if (!Number.isInteger(port.value) || port.value < 1 || port.value > 65535) throw new Error('端口必须在 1–65535 之间。')
    if (store.maintenance) throw new Error('请先退出核心维护模式，再创建节点。')
    // Refresh immediately before writing so stale cached ports do not silently collide.
    const load = await HttpUtils.get<import('@/store/modules/data').LoadedData>('api/load')
    if (!load.success || !load.obj) throw new Error('无法读取最新配置，请重新登录或刷新页面。')
    store.setNewData(load.obj)
    if (load.obj.maintenance) throw new Error('请先退出核心维护模式。')
    const status = await HttpUtils.get<{ sbd?: { running?: boolean } }>('api/status', { r: 'sbd' })
    if (!status.success || status.obj?.sbd?.running !== true) throw new Error('代理核心未运行或无法确认状态。请先处理首页的核心错误，再创建节点。')
    if (usedPorts().includes(port.value)) throw new Error('该端口已在面板中使用，请换一个端口。')
    if ([...store.inbounds, ...store.endpoints, ...store.outbounds].some(i => i.tag === tag.value)) throw new Error('节点名称已存在。')
    const options: QuickOptions = { protocol: protocol.value, host: host.value, tag: tag.value, port: port.value, socksPublic: socksPublic.value }
    if (protocol.value === 'hysteria2') {
      if (certificateMode.value === 'acme') {
        if (!certificateReady.value) throw new Error('请先确认域名解析、TCP 80 和证书服务条款。')
        if (usedPorts().includes(80)) throw new Error('面板中已有节点占用 80 端口，请先处理证书验证端口冲突。')
        options.acme = { domain: certificateHost.value, email: certificateEmail.value.trim() }
      } else {
        if (!tlsItems.value.some(i => i.value === tlsId.value)) throw new Error('请选择已配置且保持证书验证的有效 TLS 配置（ALPN 须允许 h3）。')
        const tls = store.tlsConfigs.find(t => t.id === tlsId.value)!
        options.tlsId = tls.id
        options.serverName = tls.server.server_name
      }
    }
    if (protocol.value === 'reality') {
      options.target = hostOnly(target.value)
      const keys = await HttpUtils.get<string[]>('api/keypairs', { k: 'reality' })
      if (!keys.success || !Array.isArray(keys.obj)) throw new Error('Reality 密钥接口不可用，请检查 S-UI 版本。')
      options.privateKey = keys.obj.find(k => k.startsWith('PrivateKey: '))?.slice(12).trim()
      options.publicKey = keys.obj.find(k => k.startsWith('PublicKey: '))?.slice(11).trim()
    }
    const plan = buildQuickPlan(options)
    const save = async (object: string, action: string, data: unknown, ids?: number[]) => {
      started.value = true
      wrote = true
      if (!await store.save(object, action, data, ids)) throw new Error(`保存 ${object} 失败。`)
    }
    await writeQuickPlan(plan, {
      async saveTls(tls) {
        await save('tls', 'new', tls)
        return store.tlsConfigs.find(t => t.name === tls.name)?.id ?? 0
      },
      async saveClient(client) {
        await save('clients', 'new', client)
        return store.clients.find(c => c.name === client.name)?.id ?? 0
      },
      async saveInbound(inbound, clientId) {
        await save('inbounds', 'new', inbound, [clientId])
        return store.inbounds.find(i => i.tag === inbound.tag)?.id ?? 0
      },
      async verifyClient(clientId, inboundId) {
        const client = await store.loadClients(clientId)
        const credential = client.config?.[plan.inbound.type as string]
        return client.enable && client.inbounds.includes(inboundId) &&
          !!credential &&
          (protocol.value === 'reality' ? credential?.uuid === plan.password && credential?.flow === 'xtls-rprx-vision' : credential?.password === plan.password) &&
          (protocol.value !== 'socks' || credential?.username === plan.username)
      },
      async enableInbound(inbound) { await save('inbounds', 'edit', inbound) },
    })
    const after = await HttpUtils.get<{ sbd?: { running?: boolean } }>('api/status', { r: 'sbd' })
    if (!after.success || after.obj?.sbd?.running !== true) throw new Error('配置已提交，但无法确认代理核心仍在运行。请检查核心日志。')
    result.value = plan
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败，请检查面板状态。'
    if (wrote) error.value += ` 本次名称：${tag.value}。可能已保存部分对象，请在入站、客户端和 TLS 页面检查；网络中断时不能判断最终启用结果。请勿直接重复创建。`
  } finally { busy.value = false }
}
</script>
