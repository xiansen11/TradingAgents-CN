import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({
  showSpinner: false,
  minimum: 0.2,
  easing: 'ease',
  speed: 500
})

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '仪表盘',
      icon: 'Odometer',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'DashboardHome',
        component: () => import('@/views/Dashboard/index.vue'),
        meta: {
          title: '仪表盘',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/analysis',
    name: 'Analysis',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/analysis/single',
    meta: {
      title: '单股分析',
      icon: 'TrendCharts',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: 'single',
        name: 'SingleAnalysis',
        component: () => import('@/views/Analysis/SingleAnalysis.vue'),
        meta: {
          title: '单股分析',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '分析报告',
      icon: 'Document',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'ReportsHome',
        component: () => import('@/views/Reports/index.vue'),
        meta: {
          title: '分析报告',
          requiresAuth: true
        }
      },
      {
        path: 'view/:id',
        name: 'ReportDetail',
        component: () => import('@/views/Reports/ReportDetail.vue'),
        meta: {
          title: '报告详情',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/daily-push',
    name: 'DailyPush',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '每日推送',
      icon: 'Bell',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'DailyPushHome',
        component: () => import('@/views/DailyPush/index.vue'),
        meta: {
          title: '每日推送',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/tools',
    name: 'Tools',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/tools/external-test',
    meta: {
      title: '工具测试',
      icon: 'Operation',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: 'external-test',
        name: 'ExternalToolTest',
        component: () => import('@/views/Tools/ExternalToolTest.vue'),
        meta: {
          title: '外部工具测试',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/settings/config',
    meta: {
      title: '系统配置',
      icon: 'Setting',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: 'config',
        name: 'ConfigManagement',
        component: () => import('@/views/Settings/ConfigManagement.vue'),
        meta: {
          title: '配置管理',
          requiresAuth: true
        }
      },
      {
        path: 'cache',
        name: 'CacheManagement',
        component: () => import('@/views/Settings/CacheManagement.vue'),
        meta: {
          title: '缓存管理',
          requiresAuth: true
        }
      },
      {
        path: 'database',
        name: 'DatabaseManagement',
        component: () => import('@/views/System/DatabaseManagement.vue'),
        meta: {
          title: '数据库管理',
          requiresAuth: true
        }
      },
      {
        path: 'logs',
        name: 'OperationLogs',
        component: () => import('@/views/System/OperationLogs.vue'),
        meta: {
          title: '操作日志',
          requiresAuth: true
        }
      },
      {
        path: 'system-logs',
        name: 'LogManagement',
        component: () => import('@/views/System/LogManagement.vue'),
        meta: {
          title: '系统日志',
          requiresAuth: true
        }
      },
      {
        path: 'sync',
        name: 'MultiSourceSync',
        component: () => import('@/views/System/MultiSourceSync.vue'),
        meta: {
          title: '数据同步',
          requiresAuth: true
        }
      },
      {
        path: 'scheduler',
        name: 'SchedulerManagement',
        component: () => import('@/views/System/SchedulerManagement.vue'),
        meta: {
          title: '定时任务',
          requiresAuth: true
        }
      },
      {
        path: 'usage',
        name: 'UsageStatistics',
        component: () => import('@/views/Settings/UsageStatistics.vue'),
        meta: {
          title: '使用统计',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/About/index.vue'),
    meta: {
      title: '关于项目',
      icon: 'InfoFilled',
      requiresAuth: false,
      transition: 'fade'
    }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Auth/Login.vue'),
    meta: {
      title: '登录',
      hideInMenu: true,
      transition: 'fade'
    }
  },
  { path: '/analysis/batch', redirect: '/analysis/single' },
  { path: '/analysis/history', redirect: '/reports' },
  { path: '/tasks', redirect: '/reports' },
  { path: '/queue', redirect: '/reports' },
  { path: '/screening', redirect: '/analysis/single' },
  { path: '/favorites', redirect: '/analysis/single' },
  { path: '/paper', redirect: '/analysis/single' },
  { path: '/learning/:pathMatch(.*)*', redirect: '/about' },
  { path: '/stocks/:pathMatch(.*)*', redirect: '/analysis/single' },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/Error/404.vue'),
    meta: {
      title: '页面不存在',
      hideInMenu: true,
      requiresAuth: true
    }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  }
})

router.beforeEach(async (to, _from, next) => {
  NProgress.start()

  const authStore = useAuthStore()
  const appStore = useAppStore()

  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - TradingAgents-CN`
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    authStore.setRedirectPath(to.fullPath)
    next('/login')
    return
  }

  if (authStore.isAuthenticated && to.name === 'Login') {
    next('/dashboard')
    return
  }

  appStore.setCurrentRoute(to)
  next()
})

router.afterEach(() => {
  NProgress.done()
  nextTick(() => {})
})

router.onError((error) => {
  console.error('Router error:', error)
  NProgress.done()
  ElMessage.error('页面加载失败，请重试')
})

export default router
export { routes }
