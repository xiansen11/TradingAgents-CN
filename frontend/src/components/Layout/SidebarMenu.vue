<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="appStore.sidebarCollapsed"
    :unique-opened="true"
    router
    class="sidebar-menu"
  >
    <el-menu-item index="/dashboard">
      <el-icon><Odometer /></el-icon>
      <template #title>仪表盘</template>
    </el-menu-item>

    <el-menu-item index="/analysis/single">
      <el-icon><TrendCharts /></el-icon>
      <template #title>单股分析</template>
    </el-menu-item>

    <el-menu-item index="/reports">
      <el-icon><Document /></el-icon>
      <template #title>分析报告</template>
    </el-menu-item>

    <el-menu-item index="/daily-push">
      <el-icon><Bell /></el-icon>
      <template #title>每日推送</template>
    </el-menu-item>

    <el-menu-item index="/tools/external-test">
      <el-icon><Operation /></el-icon>
      <template #title>工具测试</template>
    </el-menu-item>

    <el-sub-menu index="/settings-config">
      <template #title>
        <el-icon><Setting /></el-icon>
        <span>系统配置</span>
      </template>
      <el-menu-item index="/settings/config">配置管理</el-menu-item>
      <el-menu-item index="/settings/cache">缓存管理</el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="/settings-admin">
      <template #title>
        <el-icon><Monitor /></el-icon>
        <span>系统管理</span>
      </template>
      <el-menu-item index="/settings/database">数据库管理</el-menu-item>
      <el-menu-item index="/settings/logs">操作日志</el-menu-item>
      <el-menu-item index="/settings/system-logs">系统日志</el-menu-item>
      <el-menu-item index="/settings/sync">数据同步</el-menu-item>
      <el-menu-item index="/settings/scheduler">定时任务</el-menu-item>
      <el-menu-item index="/settings/usage">使用统计</el-menu-item>
    </el-sub-menu>

    <el-menu-item index="/about">
      <el-icon><InfoFilled /></el-icon>
      <template #title>关于项目</template>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import {
  Bell,
  Document,
  InfoFilled,
  Monitor,
  Odometer,
  Operation,
  Setting,
  TrendCharts
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()

const activeMenu = computed(() => route.path)
</script>

<style lang="scss" scoped>
.sidebar-menu {
  border: none;
  height: 100%;

  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    height: 48px;
    line-height: 48px;
  }

  :deep(.el-menu-item.is-active) {
    background-color: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }
}
</style>
