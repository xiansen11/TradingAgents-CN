<template>
  <div class="tool-test-page">
    <div class="page-header">
      <div>
        <h1>外部工具测试</h1>
        <p>A 股数据源、MCP 工具与本地服务诊断</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadSources" :loading="sourcesLoading">刷新源</el-button>
        <el-button :icon="Download" :disabled="!result" @click="exportResult">导出 JSON</el-button>
      </div>
    </div>

    <el-card class="control-card" shadow="never">
      <el-form :inline="true" class="control-form" @submit.prevent>
        <el-form-item label="股票代码">
          <el-input
            v-model.trim="form.code"
            placeholder="例如 000001"
            maxlength="6"
            clearable
            class="code-input"
            @keyup.enter="runTest"
          />
        </el-form-item>
        <el-form-item label="模块">
          <el-checkbox-group v-model="form.modules">
            <el-checkbox-button label="quote">行情</el-checkbox-button>
            <el-checkbox-button label="technical">技术面</el-checkbox-button>
            <el-checkbox-button label="fundamentals">基本面</el-checkbox-button>
            <el-checkbox-button label="news">新闻</el-checkbox-button>
            <el-checkbox-button label="mcp">MCP</el-checkbox-button>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="超时">
          <el-input-number v-model="form.timeout_seconds" :min="1" :max="120" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item>
          <el-switch v-model="form.include_raw" active-text="包含原始返回" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Operation" :loading="testing" @click="runTest">运行测试</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="sources"
      class="source-alert"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        当前支持 {{ sources.market_scope }}；数据源：{{ sources.data_sources.join(', ') }}；MCP：{{ sources.mcp_servers.length ? sources.mcp_servers.join(', ') : '未配置' }}
      </template>
    </el-alert>

    <el-empty v-if="!result && !testing" description="输入 A 股 6 位代码后运行测试" />

    <template v-if="result">
      <el-row :gutter="16" class="summary-row">
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never">
            <div class="summary-title">总体状态</div>
            <div class="summary-value">{{ statusText(result.summary.overall_status) }}</div>
            <el-tag class="status-tag" :type="statusType(result.summary.overall_status)">
              {{ result.summary.name }} {{ result.summary.code }}
            </el-tag>
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never">
            <el-statistic title="成功" :value="result.summary.success_count" />
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never">
            <el-statistic title="失败/跳过" :value="result.summary.failure_count" />
            <div class="sub-counts">
              跳过 {{ result.summary.skipped_count || 0 }}，未支持 {{ result.summary.unsupported_count || 0 }}
            </div>
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never">
            <el-statistic title="总耗时(ms)" :value="result.summary.total_latency_ms" :precision="0" />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="snapshot-row">
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never" class="snapshot-card">
            <template #header>行情</template>
            <el-descriptions v-if="result.snapshot.quote" :column="1" size="small">
              <el-descriptions-item label="价格">{{ display(result.snapshot.quote.price || result.snapshot.quote.close) }}</el-descriptions-item>
              <el-descriptions-item label="涨跌幅">{{ display(result.snapshot.quote.change_percent) }}</el-descriptions-item>
              <el-descriptions-item label="成交额">{{ display(result.snapshot.quote.amount) }}</el-descriptions-item>
              <el-descriptions-item label="来源">{{ display(result.snapshot.quote.source) }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无行情" />
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never" class="snapshot-card">
            <template #header>技术面</template>
            <el-descriptions v-if="technicalIndicators" :column="1" size="small">
              <el-descriptions-item label="MA5/20">{{ display(technicalIndicators.ma5) }} / {{ display(technicalIndicators.ma20) }}</el-descriptions-item>
              <el-descriptions-item label="MA60">{{ display(technicalIndicators.ma60) }}</el-descriptions-item>
              <el-descriptions-item label="MACD">{{ display(technicalIndicators.macd) }}</el-descriptions-item>
              <el-descriptions-item label="RSI12">{{ display(technicalIndicators.rsi12) }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else :description="result.snapshot.technical?.message || '暂无技术指标'" />
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never" class="snapshot-card">
            <template #header>基本面</template>
            <el-descriptions v-if="result.snapshot.fundamentals" :column="1" size="small">
              <el-descriptions-item label="名称">{{ display(result.snapshot.fundamentals.name) }}</el-descriptions-item>
              <el-descriptions-item label="行业">{{ display(result.snapshot.fundamentals.industry) }}</el-descriptions-item>
              <el-descriptions-item label="PE">{{ display(result.snapshot.fundamentals.pe || result.snapshot.fundamentals.pe_ttm) }}</el-descriptions-item>
              <el-descriptions-item label="PB">{{ display(result.snapshot.fundamentals.pb || result.snapshot.fundamentals.pb_mrq) }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无基本面" />
          </el-card>
        </el-col>
        <el-col :lg="6" :md="12" :sm="24">
          <el-card shadow="never" class="snapshot-card">
            <template #header>新闻</template>
            <div v-if="result.snapshot.news?.items?.length" class="news-list">
              <a
                v-for="item in result.snapshot.news.items.slice(0, 4)"
                :key="`${item.title}-${item.time}`"
                :href="item.url || undefined"
                target="_blank"
                rel="noreferrer"
              >
                {{ item.title || '未命名新闻' }}
              </a>
            </div>
            <el-empty v-else description="暂无新闻" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="diagnostics-card">
        <template #header>
          <div class="table-header">
            <span>诊断结果</span>
            <el-input v-model="filterText" :prefix-icon="Search" placeholder="筛选来源/模块/消息" clearable class="filter-input" />
          </div>
        </template>
        <el-table :data="filteredDiagnostics" stripe row-key="diagnosticKey">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="raw-panel">
                <h4>摘要样本</h4>
                <pre>{{ formatJson(row.sample) }}</pre>
                <h4 v-if="row.raw">原始返回</h4>
                <pre v-if="row.raw">{{ formatJson(row.raw) }}</pre>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" min-width="130" />
          <el-table-column prop="module" label="模块" min-width="130" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="diagnosticStatusType(row.status)">
                {{ diagnosticStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="耗时(ms)" width="120" sortable />
          <el-table-column prop="message" label="消息" min-width="260" show-overflow-tooltip />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Operation, Refresh, Search } from '@element-plus/icons-vue'
import { toolTestsApi, type ToolTestResult, type ToolTestSources, type ToolTestStatus } from '@/api/toolTests'

const sources = ref<ToolTestSources | null>(null)
const result = ref<ToolTestResult | null>(null)
const testing = ref(false)
const sourcesLoading = ref(false)
const filterText = ref('')

const form = reactive({
  code: '000001',
  include_raw: false,
  timeout_seconds: 20,
  modules: ['quote', 'technical', 'fundamentals', 'news', 'mcp']
})

const technicalIndicators = computed<Record<string, any> | null>(() => {
  return result.value?.snapshot.technical?.indicators || null
})

const filteredDiagnostics = computed(() => {
  const rows = (result.value?.diagnostics || []).map((item, index) => ({
    ...item,
    diagnosticKey: `${item.source}-${item.module}-${index}`
  }))
  const keyword = filterText.value.trim().toLowerCase()
  if (!keyword) return rows
  return rows.filter(item =>
    item.source.toLowerCase().includes(keyword) ||
    item.module.toLowerCase().includes(keyword) ||
    item.message.toLowerCase().includes(keyword)
  )
})

const loadSources = async () => {
  try {
    sourcesLoading.value = true
    const response = await toolTestsApi.getSources()
    if (response.success) {
      sources.value = response.data
    }
  } catch (err: any) {
    ElMessage.error(`加载工具源失败: ${err.message}`)
  } finally {
    sourcesLoading.value = false
  }
}

const runTest = async () => {
  if (!/^\d{6}$/.test(form.code)) {
    ElMessage.warning('请输入 6 位 A 股代码')
    return
  }
  if (!form.modules.length) {
    ElMessage.warning('至少选择一个测试模块')
    return
  }

  try {
    testing.value = true
    const response = await toolTestsApi.testStock({
      code: form.code,
      include_raw: form.include_raw,
      timeout_seconds: form.timeout_seconds,
      modules: form.modules
    })
    if (response.success) {
      result.value = response.data
      const summary = response.data.summary
      if (summary.failure_count > 0) {
        ElMessage.warning(`测试完成，${summary.success_count}/${summary.total_count} 项成功`)
      } else {
        ElMessage.success('全部测试通过')
      }
    }
  } catch (err: any) {
    ElMessage.error(`工具测试失败: ${err.message}`)
  } finally {
    testing.value = false
  }
}

const statusText = (status: ToolTestStatus) => {
  if (status === 'success') return '全部成功'
  if (status === 'partial') return '部分成功'
  return '全部失败'
}

const statusType = (status: ToolTestStatus): 'success' | 'warning' | 'danger' => {
  if (status === 'success') return 'success'
  if (status === 'partial') return 'warning'
  return 'danger'
}

const display = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return String(value)
}

const diagnosticStatusText = (status: string) => {
  if (status === 'success') return '成功'
  if (status === 'skipped') return '跳过'
  if (status === 'unsupported') return '未支持'
  return '失败'
}

const diagnosticStatusType = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'success') return 'success'
  if (status === 'skipped' || status === 'unsupported') return 'info'
  return 'danger'
}

const formatJson = (value: unknown) => {
  if (value === undefined || value === null) return '无'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const exportResult = () => {
  if (!result.value) return
  const blob = new Blob([JSON.stringify(result.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tool-test-${result.value.summary.code}-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(loadSources)
</script>

<style scoped lang="scss">
.tool-test-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 650;
    }

    p {
      margin: 6px 0 0;
      color: var(--el-text-color-secondary);
    }
  }

  .header-actions,
  .table-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .control-card,
  .source-alert,
  .summary-row,
  .snapshot-row,
  .diagnostics-card {
    margin-bottom: 16px;
  }

  .control-form {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .code-input {
    width: 160px;
  }

  .status-tag {
    margin-top: 12px;
  }

  .summary-title {
    color: var(--el-text-color-regular);
    font-size: 14px;
  }

  .summary-value {
    margin-top: 8px;
    color: var(--el-text-color-primary);
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;
  }

  .sub-counts {
    margin-top: 8px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }

  .snapshot-card {
    min-height: 230px;
  }

  .news-list {
    display: flex;
    flex-direction: column;
    gap: 10px;

    a {
      color: var(--el-color-primary);
      text-decoration: none;
      line-height: 1.4;
    }
  }

  .table-header {
    justify-content: space-between;
  }

  .filter-input {
    width: 280px;
  }

  .raw-panel {
    padding: 8px 20px 16px;
    background: var(--el-fill-color-lighter);

    h4 {
      margin: 8px 0;
    }

    pre {
      max-height: 360px;
      overflow: auto;
      margin: 0;
      padding: 12px;
      border-radius: 6px;
      background: var(--el-bg-color);
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.5;
    }
  }
}

@media (max-width: 768px) {
  .tool-test-page {
    .page-header,
    .table-header {
      align-items: stretch;
      flex-direction: column;
    }

    .filter-input {
      width: 100%;
    }
  }
}
</style>
