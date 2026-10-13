<template>
  <el-container class="app-layout">
    <el-aside class="app-aside" :width="collapsed ? '64px' : '220px'">
      <div class="app-aside__logo">
        <div class="app-aside__logo-badge">TAXI</div>
        <div v-show="!collapsed">
          <div class="app-aside__logo-text">出租车运营管理</div>
          <div class="app-aside__logo-sub">分析与调度决策支持</div>
        </div>
      </div>
      <el-scrollbar>
        <el-menu
          router
          :default-active="activeMenu"
          :collapse="collapsed"
          :collapse-transition="false"
          unique-opened
        >
          <template v-for="group in menus" :key="group.title">
            <el-sub-menu v-if="group.children.length > 1" :index="group.title">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon>
                <span>{{ group.title }}</span>
              </template>
              <el-menu-item v-for="item in group.children" :key="item.path" :index="item.path">
                <el-icon><component :is="item.icon" /></el-icon>
                <template #title>{{ item.title }}</template>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="group.children[0].path">
              <el-icon><component :is="group.children[0].icon" /></el-icon>
              <template #title>{{ group.children[0].title }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="app-header__toggle" @click="collapsed = !collapsed">
          <el-icon>
            <component :is="collapsed ? 'Expand' : 'Fold'" />
          </el-icon>
        </div>
        <el-breadcrumb separator="/" class="app-breadcrumb" style="margin-bottom: 0">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="route.meta?.group">{{ route.meta.group }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta?.title || '页面' }}</el-breadcrumb-item>
        </el-breadcrumb>

        <div class="app-header__right">
          <el-tooltip content="系统使用说明与接口文档" placement="bottom">
            <el-button link @click="openDocs">
              <el-icon><Document /></el-icon>
            </el-button>
          </el-tooltip>
          <el-badge :value="alertCount" :hidden="!alertCount" :max="99" type="danger">
            <el-button link @click="router.push('/dashboard')">
              <el-icon :size="17"><Bell /></el-icon>
            </el-button>
          </el-badge>

          <el-dropdown @command="handleCommand">
            <div class="app-header__user">
              <div class="app-header__avatar">{{ avatarText }}</div>
              <div>
                <div class="app-header__name">{{ user.real_name || user.username || '未登录' }}</div>
                <div class="app-header__role">{{ roleText }}</div>
              </div>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item command="docs">
                  <el-icon><Document /></el-icon>接口文档
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="app-main">
        <el-alert
          v-if="user.role === 'viewer'"
          type="info"
          show-icon
          :closable="false"
          class="mb-16"
          title="当前账号为只读用户（viewer）"
          description="你可以查看全部数据与图表，但新增、修改、删除等写操作会被系统拒绝。如需操作数据，请使用调度员或管理员账号登录。"
        />
        <router-view v-slot="{ Component }">
          <keep-alive :max="6">
            <component :is="Component" :key="route.path" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { authApi, dashboardApi } from '../api';
import { ROLE_TEXT } from '../utils/format';

const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const user = ref({});
const alertCount = ref(0);

const menus = [
  {
    title: '总览',
    icon: 'Odometer',
    children: [
      { path: '/dashboard', title: '运营驾驶舱', icon: 'Odometer' },
      { path: '/analysis', title: '运营数据分析', icon: 'TrendCharts' },
    ],
  },
  {
    title: '监测与预测',
    icon: 'DataAnalysis',
    children: [
      { path: '/demand', title: '叫车需求分析', icon: 'DataLine' },
      { path: '/forecast', title: '需求预测中心', icon: 'MagicStick' },
      { path: '/dispatch', title: '调度决策中心', icon: 'Guide' },
    ],
  },
  {
    title: '运营管理',
    icon: 'Van',
    children: [
      { path: '/operations', title: '营运订单管理', icon: 'Tickets' },
      { path: '/vehicles', title: '车辆管理', icon: 'Van' },
      { path: '/drivers', title: '驾驶员管理', icon: 'UserFilled' },
      { path: '/assignments', title: '人车绑定排班', icon: 'Connection' },
      { path: '/regions', title: '运营区域管理', icon: 'MapLocation' },
    ],
  },
  {
    title: '系统管理',
    icon: 'Setting',
    children: [
      { path: '/system/users', title: '用户管理', icon: 'User' },
      { path: '/system/configs', title: '参数配置', icon: 'Tools' },
      { path: '/system/logs', title: '操作日志', icon: 'Tickets' },
      { path: '/system/data', title: '数据维护', icon: 'Coin' },
    ],
  },
];

const activeMenu = computed(() => route.path);
const roleText = computed(() => ROLE_TEXT[user.value.role] || user.value.role || '');
const avatarText = computed(() => {
  const name = user.value.real_name || user.value.username || '?';
  return name.slice(0, 1).toUpperCase();
});

async function loadUser() {
  try {
    user.value = await authApi.me();
    // 供其他页面判断角色（后端已对只读用户做写操作拦截）
    localStorage.setItem('role', user.value.role || '');
  } catch (error) {
    /* 拦截器已处理 */
  }
}

async function loadAlerts() {
  try {
    const data = await dashboardApi.alerts({ limit: 1, days: 7 });
    alertCount.value = data?.total || 0;
  } catch (error) {
    alertCount.value = 0;
  }
}

function openDocs() {
  window.open('/docs', '_blank');
}

async function handleCommand(command) {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' });
    } catch (error) {
      return;
    }
    try {
      await authApi.logout();
    } catch (error) {
      /* 忽略 */
    }
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    ElMessage.success('已退出登录');
    router.push('/login');
    return;
  }
  if (command === 'docs') {
    openDocs();
    return;
  }
  router.push('/profile');
}

onMounted(() => {
  loadUser();
  loadAlerts();
});
</script>
