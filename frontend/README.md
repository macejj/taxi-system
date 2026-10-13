# 前端说明

城市出租车运营管理与决策支持系统 —— 前端工程（Vue 3 + Vite + Element Plus + ECharts）。

## 运行

```bash
npm install       # 首次运行
npm run dev       # 开发服务，访问 http://localhost:5173
npm run build     # 生产构建，输出到 dist/
npm run preview   # 预览生产构建
```

开发服务已把 `/api` 代理到 `http://localhost:8000`（见 `vite.config.js`），
因此**必须同时启动后端服务**才能看到数据。

## 目录结构

```
src/
├── api/
│   ├── request.js      axios 实例：令牌注入、统一错误提示、401 自动跳登录
│   └── index.js        统一 API 层，按 12 个业务模块分组
├── components/
│   ├── ChartBox.vue    ECharts 容器（自动 resize、加载态、空态）
│   ├── StatCard.vue    KPI 指标卡（支持环比与「越低越好」语义）
│   └── PageHeader.vue  页面标题 + 说明 + 右侧操作区
├── utils/format.js     数字/金额/时间格式化与状态字典
├── router/index.js     路由表与登录守卫
├── style.css           设计变量与全局样式（布局、卡片、筛选条、表格容器）
├── views/              18 个页面
│   ├── Login.vue / Layout.vue / Dashboard.vue
│   ├── AnalysisCenter.vue      运营数据分析（5 个标签页）
│   ├── DemandAnalysis.vue      叫车需求分析
│   ├── ForecastCenter.vue      需求预测中心
│   ├── DispatchCenter.vue      调度决策中心（4 个标签页）
│   ├── OperationList.vue       营运订单管理
│   ├── VehicleList.vue / DriverList.vue / AssignmentList.vue / RegionList.vue
│   ├── Profile.vue / NotFound.vue
│   └── system/                 用户管理、参数配置、操作日志、数据维护
└── main.js             应用入口（全量注册 Element Plus 组件与图标）
```

## 开发约定

新增页面前请先阅读 [`FRONTEND_GUIDE.md`](./FRONTEND_GUIDE.md)，
其中约定了页面骨架、可复用的全局样式类、API 调用方式与全部接口的数据结构。

`Dashboard.vue` 是风格与写法的标准范例。

## 角色与权限

| 角色 | 说明 |
| --- | --- |
| `admin` | 系统管理员，全部功能 |
| `operator` | 调度员，业务数据读写、预测与调度 |
| `viewer` | 只读用户，可查看全部数据；写操作会被后端中间件拒绝 |

只读用户登录后，页面顶部会显示只读提示条。**权限边界在后端**，
前端的按钮禁用与提示只是体验优化。
