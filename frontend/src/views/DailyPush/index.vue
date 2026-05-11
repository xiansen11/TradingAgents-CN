<template>
  <div class="daily-push-page">
    <el-card class="header-card" shadow="never">
      <div class="header-main">
        <div>
          <h2>
            <el-icon><Bell /></el-icon>
            每日推送
          </h2>
          <p>订阅股票报告，按天自动生成并推送到飞书。</p>
        </div>
        <div class="header-actions">
          <el-button :icon="Refresh" :loading="loading" @click="reloadAll">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建订阅</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="table-card" shadow="never">
      <el-table :data="subscriptions" v-loading="loading" stripe>
        <el-table-column label="订阅" min-width="180">
          <template #default="{ row }">
            <div class="subscription-name">
              <strong>{{ row.name }}</strong>
              <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                {{ row.enabled ? '已启用' : '已停用' }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="股票" min-width="220">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="symbol in row.stock_symbols" :key="symbol" size="small">
                {{ symbol }}
              </el-tag>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            <div class="time-stack">
              <span>生成 {{ row.analysis_time }}</span>
              <span>推送 {{ row.push_time }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="飞书" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="feishu-info">
              <span>{{ row.feishu?.app_id || '-' }}</span>
              <small>{{ row.feishu?.chat_id || '-' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="下次生成" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.next_run_at) }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              :loading="toggleLoading[row.id]"
              @change="toggleSubscription(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
            <el-button size="small" type="success" :icon="Message" @click="openTestDialog(row)">
              测试发送
            </el-button>
            <el-button
              size="small"
              type="primary"
              :icon="Promotion"
              :loading="actionLoading[row.id]"
              @click="runNow(row)"
            >
              立即运行
            </el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="deleteSubscription(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="card-title">
          <span>执行历史</span>
          <el-button text :icon="Refresh" @click="loadRuns">刷新</el-button>
        </div>
      </template>
      <el-table :data="runs" v-loading="runsLoading" stripe>
        <el-table-column label="股票" prop="stock_symbol" width="100" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ formatRunType(row.run_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">
              {{ formatStatus(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="任务 ID" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.task_id || '-' }}</template>
        </el-table-column>
        <el-table-column label="报告" width="120">
          <template #default="{ row }">
            <el-link v-if="row.report_id" type="primary" @click="openReport(row.report_id)">
              查看报告
            </el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error_message || '-' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at || row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑订阅' : '新建订阅'"
      width="760px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" label-width="120px">
        <el-form-item label="订阅名称" required>
          <el-input v-model="form.name" placeholder="例如：每日自选股报告" />
        </el-form-item>
        <el-form-item label="订阅股票" required>
          <div class="stock-editor">
            <div class="stock-tags">
              <el-tag
                v-for="symbol in form.stock_symbols"
                :key="symbol"
                closable
                @close="removeStock(symbol)"
              >
                {{ symbol }}
              </el-tag>
            </div>
            <el-input
              v-model="stockInput"
              maxlength="6"
              placeholder="输入 6 位 A 股代码后回车"
              @keyup.enter="addStock"
            >
              <template #append>
                <el-button @click="addStock">添加</el-button>
              </template>
            </el-input>
          </div>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="生成时间" required>
              <el-time-picker
                v-model="form.analysis_time"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择生成时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="推送时间" required>
              <el-time-picker
                v-model="form.push_time"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择推送时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="研究深度">
              <el-select v-model="form.analysis_parameters.research_depth" style="width: 100%">
                <el-option label="快速" value="快速" />
                <el-option label="基础" value="基础" />
                <el-option label="标准" value="标准" />
                <el-option label="深度" value="深度" />
                <el-option label="全面" value="全面" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时区">
              <el-input v-model="form.timezone" placeholder="Asia/Shanghai" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="分析师">
          <el-checkbox-group v-model="form.analysis_parameters.selected_analysts">
            <el-checkbox label="market">市场</el-checkbox>
            <el-checkbox label="fundamentals">基本面</el-checkbox>
            <el-checkbox label="news">新闻</el-checkbox>
            <el-checkbox label="social">情绪</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="快速模型">
              <el-input v-model="form.analysis_parameters.quick_analysis_model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="深度模型">
              <el-input v-model="form.analysis_parameters.deep_analysis_model" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">飞书自建应用</el-divider>
        <el-form-item label="App ID" required>
          <el-input v-model="form.feishu.app_id" placeholder="cli_xxx" />
        </el-form-item>
        <el-form-item label="App Secret" required>
          <el-input
            v-model="form.feishu.app_secret"
            type="password"
            show-password
            :placeholder="editingId ? '留空则不修改现有密钥' : '请输入 App Secret'"
          />
        </el-form-item>
        <el-form-item label="Chat ID" required>
          <el-input v-model="form.feishu.chat_id" placeholder="oc_xxx" />
        </el-form-item>
        <el-form-item label="Domain">
          <el-input v-model="form.feishu.domain" placeholder="https://open.feishu.cn" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="editingId"
          type="success"
          :icon="Message"
          :loading="saveLoading"
          @click="saveAndTest"
        >
          保存并测试发送
        </el-button>
        <el-button type="primary" :loading="saveLoading" @click="saveSubscription">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="testDialogVisible" title="测试发送" width="460px">
      <el-form label-width="100px">
        <el-form-item label="订阅">
          <el-input :model-value="testTarget?.name" disabled />
        </el-form-item>
        <el-form-item label="测试股票">
          <el-select v-model="testStock" style="width: 100%">
            <el-option
              v-for="symbol in testTarget?.stock_symbols || []"
              :key="symbol"
              :label="symbol"
              :value="symbol"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">取消</el-button>
        <el-button type="success" :icon="Message" :loading="testLoading" @click="confirmTestSend">
          生成并发送
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  Bell,
  Delete,
  Edit,
  Message,
  Plus,
  Promotion,
  Refresh
} from '@element-plus/icons-vue'
import {
  dailyPushApi,
  type DailyPushRun,
  type DailyPushRunStatus,
  type DailyPushSubscription,
  type DailyPushSubscriptionPayload
} from '@/api/dailyPush'

const router = useRouter()
const formRef = ref<FormInstance>()

const subscriptions = ref<DailyPushSubscription[]>([])
const runs = ref<DailyPushRun[]>([])
const loading = ref(false)
const runsLoading = ref(false)
const saveLoading = ref(false)
const testLoading = ref(false)
const actionLoading = ref<Record<string, boolean>>({})
const toggleLoading = ref<Record<string, boolean>>({})

const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const stockInput = ref('')
const testDialogVisible = ref(false)
const testTarget = ref<DailyPushSubscription | null>(null)
const testStock = ref('')
let pollTimer: number | undefined

const createDefaultForm = (): DailyPushSubscriptionPayload => ({
  name: '',
  enabled: true,
  stock_symbols: [],
  analysis_time: '18:00',
  push_time: '18:30',
  timezone: 'Asia/Shanghai',
  analysis_parameters: {
    research_depth: '标准',
    selected_analysts: ['market', 'fundamentals', 'news', 'social'],
    quick_analysis_model: 'qwen-turbo',
    deep_analysis_model: 'qwen-max'
  },
  feishu: {
    app_id: '',
    app_secret: '',
    chat_id: '',
    domain: 'https://open.feishu.cn'
  }
})

const form = ref<DailyPushSubscriptionPayload>(createDefaultForm())

const hasActiveRuns = computed(() =>
  runs.value.some((run) => ['queued', 'generating', 'waiting_to_push', 'sending'].includes(run.status))
)

onMounted(async () => {
  await reloadAll()
  pollTimer = window.setInterval(() => {
    if (hasActiveRuns.value) {
      loadRuns()
    }
  }, 5000)
})

onBeforeUnmount(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
  }
})

async function reloadAll() {
  await Promise.all([loadSubscriptions(), loadRuns()])
}

async function loadSubscriptions() {
  loading.value = true
  try {
    const res = await dailyPushApi.getSubscriptions()
    subscriptions.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function loadRuns() {
  runsLoading.value = true
  try {
    const res = await dailyPushApi.getRuns({ limit: 100 })
    runs.value = res.data?.items || []
  } finally {
    runsLoading.value = false
  }
}

function openCreateDialog() {
  editingId.value = null
  form.value = createDefaultForm()
  stockInput.value = ''
  dialogVisible.value = true
}

function openEditDialog(row: DailyPushSubscription) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    enabled: row.enabled,
    stock_symbols: [...row.stock_symbols],
    analysis_time: row.analysis_time,
    push_time: row.push_time,
    timezone: row.timezone || 'Asia/Shanghai',
    analysis_parameters: {
      research_depth: row.analysis_parameters?.research_depth || '标准',
      selected_analysts: [...(row.analysis_parameters?.selected_analysts || ['market', 'fundamentals'])],
      quick_analysis_model: row.analysis_parameters?.quick_analysis_model || 'qwen-turbo',
      deep_analysis_model: row.analysis_parameters?.deep_analysis_model || 'qwen-max'
    },
    feishu: {
      app_id: row.feishu?.app_id || '',
      app_secret: '',
      chat_id: row.feishu?.chat_id || '',
      domain: row.feishu?.domain || 'https://open.feishu.cn'
    }
  }
  stockInput.value = ''
  dialogVisible.value = true
}

function addStock() {
  const symbol = stockInput.value.trim()
  if (!/^\d{6}$/.test(symbol)) {
    ElMessage.warning('请输入 6 位 A 股代码')
    return
  }
  if (!form.value.stock_symbols.includes(symbol)) {
    form.value.stock_symbols.push(symbol)
  }
  stockInput.value = ''
}

function removeStock(symbol: string) {
  form.value.stock_symbols = form.value.stock_symbols.filter((item) => item !== symbol)
}

function validateForm() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入订阅名称')
    return false
  }
  if (!form.value.stock_symbols.length) {
    ElMessage.warning('请至少添加一只股票')
    return false
  }
  if (!form.value.analysis_time || !form.value.push_time) {
    ElMessage.warning('请选择生成时间和推送时间')
    return false
  }
  if (!form.value.feishu.app_id || !form.value.feishu.chat_id) {
    ElMessage.warning('请填写飞书 App ID 和 Chat ID')
    return false
  }
  if (!editingId.value && !form.value.feishu.app_secret) {
    ElMessage.warning('新建订阅需要填写飞书 App Secret')
    return false
  }
  if (!form.value.analysis_parameters.selected_analysts.length) {
    ElMessage.warning('请至少选择一个分析师')
    return false
  }
  return true
}

function buildPayload(): DailyPushSubscriptionPayload {
  const payload: DailyPushSubscriptionPayload = JSON.parse(JSON.stringify(form.value))
  payload.name = payload.name.trim()
  payload.timezone = payload.timezone || 'Asia/Shanghai'
  payload.feishu.domain = payload.feishu.domain || 'https://open.feishu.cn'
  if (editingId.value && !payload.feishu.app_secret) {
    delete payload.feishu.app_secret
  }
  return payload
}

async function saveSubscription() {
  if (!validateForm()) return null
  saveLoading.value = true
  try {
    const payload = buildPayload()
    const res = editingId.value
      ? await dailyPushApi.updateSubscription(editingId.value, payload)
      : await dailyPushApi.createSubscription(payload)
    ElMessage.success('订阅已保存')
    dialogVisible.value = false
    await loadSubscriptions()
    return res.data
  } finally {
    saveLoading.value = false
  }
}

async function saveAndTest() {
  const saved = await saveSubscription()
  const target = saved || subscriptions.value.find((item) => item.id === editingId.value)
  if (target) {
    await startTestSend(target, target.stock_symbols[0])
  }
}

async function toggleSubscription(row: DailyPushSubscription) {
  toggleLoading.value[row.id] = true
  try {
    await dailyPushApi.updateSubscription(row.id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '订阅已启用' : '订阅已停用')
  } catch (error) {
    row.enabled = !row.enabled
    throw error
  } finally {
    toggleLoading.value[row.id] = false
  }
}

async function deleteSubscription(row: DailyPushSubscription) {
  await ElMessageBox.confirm(`确定删除订阅「${row.name}」吗？`, '删除订阅', {
    type: 'warning'
  })
  await dailyPushApi.deleteSubscription(row.id)
  ElMessage.success('订阅已删除')
  await reloadAll()
}

function openTestDialog(row: DailyPushSubscription) {
  testTarget.value = row
  testStock.value = row.stock_symbols[0] || ''
  testDialogVisible.value = true
}

async function confirmTestSend() {
  if (!testTarget.value) return
  await startTestSend(testTarget.value, testStock.value)
  testDialogVisible.value = false
}

async function startTestSend(row: DailyPushSubscription, symbol?: string) {
  testLoading.value = true
  try {
    const res = await dailyPushApi.testSend(row.id, symbol)
    ElMessage.success(`测试发送已启动：${res.data.stock_symbol}`)
    await loadRuns()
  } finally {
    testLoading.value = false
  }
}

async function runNow(row: DailyPushSubscription) {
  await ElMessageBox.confirm(`立即为「${row.name}」的全部股票生成并推送报告？`, '立即运行', {
    type: 'warning'
  })
  actionLoading.value[row.id] = true
  try {
    const res = await dailyPushApi.runNow(row.id)
    const started = res.data?.started?.length || 0
    const skipped = res.data?.skipped?.length || 0
    ElMessage.success(`已启动 ${started} 个任务，跳过 ${skipped} 个运行中的任务`)
    await loadRuns()
  } finally {
    actionLoading.value[row.id] = false
  }
}

function openReport(reportId: string) {
  router.push(`/reports/view/${reportId}`)
}

function formatDateTime(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatRunType(type: DailyPushRun['run_type']) {
  const labels: Record<DailyPushRun['run_type'], string> = {
    scheduled: '定时',
    manual: '手动',
    test: '测试'
  }
  return labels[type] || type
}

function formatStatus(status: DailyPushRunStatus) {
  const labels: Record<DailyPushRunStatus, string> = {
    queued: '排队中',
    generating: '生成中',
    waiting_to_push: '待推送',
    sending: '发送中',
    sent: '已发送',
    failed: '失败'
  }
  return labels[status] || status
}

function statusType(status: DailyPushRunStatus) {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger' | 'primary'> = {
    queued: 'info',
    generating: 'primary',
    waiting_to_push: 'warning',
    sending: 'primary',
    sent: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}
</script>

<style scoped lang="scss">
.daily-push-page {
  padding: 20px;
}

.header-card,
.table-card {
  margin-bottom: 16px;
}

.header-main,
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-main h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.header-main p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.subscription-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-stack,
.feishu-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feishu-info small {
  color: var(--el-text-color-secondary);
}

.stock-editor {
  width: 100%;
}

.stock-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 32px;
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .daily-push-page {
    padding: 12px;
  }

  .header-main {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
