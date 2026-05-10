<template>
  <div class="dashboard">
    <div class="page-header">
      <div>
        <h1>A股单股智能分析平台</h1>
        <p>聚焦单股分析、报告生成、多智能体协作和系统运维。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="router.push('/analysis/single')">
          <el-icon><TrendCharts /></el-icon>
          开始分析
        </el-button>
        <el-button @click="router.push('/reports')">
          <el-icon><Document /></el-icon>
          查看报告
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="stat-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="stat-card">
            <span class="stat-label">报告总数</span>
            <strong>{{ stats.totalReports }}</strong>
            <span class="stat-note">MongoDB analysis_reports</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="stat-card">
            <span class="stat-label">最近分析</span>
            <strong>{{ stats.recentReports }}</strong>
            <span class="stat-note">最近 20 条报告</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="stat-card">
            <span class="stat-label">MongoDB</span>
            <strong>
              <el-tag :type="mongoStatus.type">{{ mongoStatus.text }}</el-tag>
            </strong>
            <span class="stat-note">任务与报告持久化</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="stat-card">
            <span class="stat-label">Redis</span>
            <strong>
              <el-tag :type="cacheStatus.type">{{ cacheStatus.text }}</el-tag>
            </strong>
            <span class="stat-note">缓存与进度状态</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="content-grid">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>最近分析报告</span>
              <el-button text type="primary" @click="router.push('/reports')">全部报告</el-button>
            </div>
          </template>
          <el-table :data="reports" v-loading="loadingReports" height="360">
            <el-table-column prop="stock_code" label="股票代码" width="120" />
            <el-table-column prop="stock_name" label="股票名称" min-width="140" />
            <el-table-column prop="analysis_date" label="分析日期" width="140" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">
                  {{ row.status || 'completed' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openReport(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>核心能力</template>
          <div class="capability-list">
            <div v-for="item in capabilities" :key="item.title" class="capability-item">
              <el-icon><component :is="item.icon" /></el-icon>
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ item.description }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="ops-card">
          <template #header>运维入口</template>
          <div class="ops-actions">
            <el-button @click="router.push('/settings/config')">配置管理</el-button>
            <el-button @click="router.push('/settings/database')">数据库管理</el-button>
            <el-button @click="router.push('/settings/cache')">缓存管理</el-button>
            <el-button @click="router.push('/settings/sync')">数据同步</el-button>
            <el-button @click="router.push('/settings/scheduler')">定时任务</el-button>
            <el-button @click="router.push('/settings/system-logs')">系统日志</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Connection,
  Cpu,
  DataAnalysis,
  Document,
  Files,
  TrendCharts
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

type TagType = 'success' | 'warning' | 'info' | 'danger'

type ReportItem = {
  id: string
  stock_code?: string
  stock_name?: string
  analysis_date?: string
  status?: string
  created_at?: string
}

const router = useRouter()
const authStore = useAuthStore()
const loadingReports = ref(false)
const reports = ref<ReportItem[]>([])
const stats = ref({
  totalReports: 0,
  recentReports: 0
})

const capabilities = [
  { title: '多智能体协作', description: '分析师、研究员、交易员、风控与管理层协同生成报告', icon: Cpu },
  { title: 'A股数据源', description: '保留 Tushare、AKShare、BaoStock 与缓存机制', icon: DataAnalysis },
  { title: '新闻分析', description: '新闻过滤、质量评估、相关性分析进入单股报告', icon: Files },
  { title: '报告导出', description: '支持 Markdown、JSON、Word、PDF 等报告导出链路', icon: Document },
  { title: 'Redis/MongoDB', description: 'Redis 负责缓存和进度，MongoDB 负责任务和报告', icon: Connection }
]

const mongoStatus = computed<{ text: string; type: TagType }>(() => ({
  text: stats.value.totalReports >= 0 ? '已连接' : '未知',
  type: 'success'
}))

const cacheStatus = computed<{ text: string; type: TagType }>(() => ({
  text: '已保留',
  type: 'success'
}))

const fetchReports = async () => {
  loadingReports.value = true
  try {
    const response = await fetch('/api/reports/list?page=1&page_size=20&market_filter=A股', {
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const result = await response.json()
    const data = result.data || result
    reports.value = data.reports || []
    stats.value.totalReports = data.total || reports.value.length
    stats.value.recentReports = reports.value.length
  } catch (error) {
    console.warn('Failed to load dashboard reports:', error)
    reports.value = []
  } finally {
    loadingReports.value = false
  }
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const openReport = (report: ReportItem) => {
  router.push(`/reports/view/${report.id}`)
}

onMounted(fetchReports)
</script>

<style lang="scss" scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  h1 {
    margin: 0 0 8px;
    font-size: 24px;
    font-weight: 650;
  }

  p {
    margin: 0;
    color: var(--el-text-color-secondary);
  }
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stat-grid,
.content-grid {
  width: 100%;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;

  .stat-label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  strong {
    font-size: 26px;
    line-height: 1.2;
  }

  .stat-note {
    color: var(--el-text-color-placeholder);
    font-size: 12px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.capability-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.capability-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;

  .el-icon {
    margin-top: 2px;
    color: var(--el-color-primary);
  }

  div {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  strong {
    font-size: 14px;
  }

  span {
    color: var(--el-text-color-secondary);
    font-size: 13px;
    line-height: 1.5;
  }
}

.ops-card {
  margin-top: 16px;
}

.ops-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  .el-button {
    margin-left: 0;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }

  .header-actions,
  .ops-actions {
    width: 100%;
    grid-template-columns: 1fr;
  }
}
</style>
