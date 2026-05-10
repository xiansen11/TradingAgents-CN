<template>
  <div class="error-404">
    <el-result
      icon="warning"
      title="页面不存在"
      sub-title="该页面已经移除，精简版只保留 A股单股分析、报告和系统运维后台。"
    >
      <template #extra>
        <el-button type="primary" @click="router.push('/dashboard')">返回仪表盘</el-button>
        <el-button @click="router.push('/analysis/single')">单股分析</el-button>
        <el-button @click="router.push('/reports')">分析报告</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style lang="scss" scoped>
.error-404 {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-bg-color-page);
  padding: 24px;
}
</style>
