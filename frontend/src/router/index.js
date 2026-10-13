import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '运营驾驶舱', group: '总览' },
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: () => import('../views/AnalysisCenter.vue'),
        meta: { title: '运营数据分析', group: '总览' },
      },
      {
        path: 'demand',
        name: 'demand',
        component: () => import('../views/DemandAnalysis.vue'),
        meta: { title: '叫车需求分析', group: '监测与预测' },
      },
      {
        path: 'forecast',
        name: 'forecast',
        component: () => import('../views/ForecastCenter.vue'),
        meta: { title: '需求预测中心', group: '监测与预测' },
      },
      {
        path: 'dispatch',
        name: 'dispatch',
        component: () => import('../views/DispatchCenter.vue'),
        meta: { title: '调度决策中心', group: '监测与预测' },
      },
      {
        path: 'operations',
        name: 'operations',
        component: () => import('../views/OperationList.vue'),
        meta: { title: '营运订单管理', group: '运营管理' },
      },
      {
        path: 'vehicles',
        name: 'vehicles',
        component: () => import('../views/VehicleList.vue'),
        meta: { title: '车辆管理', group: '运营管理' },
      },
      {
        path: 'drivers',
        name: 'drivers',
        component: () => import('../views/DriverList.vue'),
        meta: { title: '驾驶员管理', group: '运营管理' },
      },
      {
        path: 'assignments',
        name: 'assignments',
        component: () => import('../views/AssignmentList.vue'),
        meta: { title: '人车绑定排班', group: '运营管理' },
      },
      {
        path: 'regions',
        name: 'regions',
        component: () => import('../views/RegionList.vue'),
        meta: { title: '运营区域管理', group: '运营管理' },
      },
      {
        path: 'system/users',
        name: 'system-users',
        component: () => import('../views/system/UserManage.vue'),
        meta: { title: '用户管理', group: '系统管理' },
      },
      {
        path: 'system/configs',
        name: 'system-configs',
        component: () => import('../views/system/ConfigManage.vue'),
        meta: { title: '参数配置', group: '系统管理' },
      },
      {
        path: 'system/logs',
        name: 'system-logs',
        component: () => import('../views/system/OperationLog.vue'),
        meta: { title: '操作日志', group: '系统管理' },
      },
      {
        path: 'system/data',
        name: 'system-data',
        component: () => import('../views/system/DataMaintain.vue'),
        meta: { title: '数据维护', group: '系统管理' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('../views/Profile.vue'),
        meta: { title: '个人中心' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFound.vue'),
    meta: { title: '页面不存在', public: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach((to) => {
  const token = localStorage.getItem('token');
  if (to.meta?.public) {
    if (to.name === 'login' && token) return { path: '/dashboard' };
    return true;
  }
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } };
  }
  return true;
});

router.afterEach((to) => {
  const title = to.meta?.title;
  document.title = title
    ? `${title} - 出租车运营管理与决策支持系统`
    : '出租车运营管理与决策支持系统';
});

export default router;
