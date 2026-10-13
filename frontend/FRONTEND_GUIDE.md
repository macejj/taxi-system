# 前端开发约定（必须遵守）

> 本项目为 Vue 3 + Vite + Element Plus + ECharts 的毕业设计前端。
> 新增页面前请先阅读 `src/views/Dashboard.vue`，它是风格与写法的**标准范例**。

## 1. 技术约束

- Vue 3 **组合式 API**，一律使用 `<script setup>`，**不使用 TypeScript**。
- UI 库：Element Plus（已在 `main.js` 中全量注册组件**和全部图标**，
  模板里可直接写 `<el-icon><Van /></el-icon>`，**不需要 import 图标组件**）。
- 图表：使用项目自带的 `src/components/ChartBox.vue`，**不要直接初始化 echarts**。
- 日期处理：Element Plus 的 `el-date-picker` 使用 `value-format="YYYY-MM-DD"`。
- **不要新增任何 npm 依赖**（无网络安装环境）。
- 不要使用 `defineOptions`、`<script lang="ts">`、可选链赋值等实验特性。

## 2. 目录与命名

```
src/
  api/index.js        统一 API 层（只从这里调用后端）
  api/request.js      axios 实例（已做令牌注入与错误提示）
  utils/format.js     格式化工具与字典
  components/         PageHeader.vue / StatCard.vue / ChartBox.vue
  views/              页面
  views/system/       系统管理页面
```

## 3. 页面骨架（请严格保持）

```vue
<template>
  <div v-loading="loading">
    <PageHeader title="页面标题" description="一句话说明这个页面解决什么问题">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </PageHeader>
    ... 内容 ...
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';   // 仅当需要作为变量传给 :icon 时才 import
import PageHeader from '../components/PageHeader.vue';
import ChartBox from '../components/ChartBox.vue';
import StatCard from '../components/StatCard.vue';
import { xxxApi } from '../api';
import { thousands, money, percent, recentRange } from '../utils/format';
</script>
```

`views/system/*.vue` 的 import 路径要多一层：`../../components/...`、`../../api`、`../../utils/format`。

### 可复用的全局样式类（定义在 `src/style.css`，直接用，不要重复写）

| 类名 | 用途 |
| --- | --- |
| `chart-card` | 白底圆角卡片容器（含内边距与阴影） |
| `chart-card__head` | 卡片头部（左右两端对齐） |
| `chart-card__title` | 卡片标题（左侧带蓝色竖条） |
| `chart-card__desc` | 卡片副标题说明 |
| `filter-bar` | 顶部筛选条（白底圆角，内部放 el-form-item 或控件） |
| `table-card` | 表格容器（白底圆角） |
| `table-toolbar` | 表格上方工具栏（左右两端） |
| `pagination-bar` | 分页条（右对齐） |
| `text-muted` / `text-danger` / `text-success` / `text-warning` | 文字颜色 |
| `mono` | 等宽数字 |
| `mb-16` / `mt-16` | 外边距 |

### 组件用法

```vue
<!-- 指标卡 -->
<StatCard label="今日订单量" :value="123" unit="单" icon="Tickets" tone="blue"
          :change="5.2" change-label="较昨日" sub="活跃车辆 56 台" :digits="0" />
<!-- tone 可选：blue / green / orange / red / purple / cyan
     change 为环比百分数，可为 null；inverse 表示「越低越好」（如空驶率） -->

<!-- 图表：option 为标准 ECharts option -->
<ChartBox :option="option" :height="320" :loading="loading" :empty="!list.length" />
```

## 4. API 层

只使用 `src/api/index.js` 导出的对象，**不要自己写 axios**。

```js
import { vehicleApi, analysisApi } from '../api';

const page = await vehicleApi.page({ page: 1, page_size: 20, keyword: '' });
// page => { total, page, page_size, items: [...] }
```

所有请求的返回值已经是**响应体本身**（拦截器已剥掉 `data`），错误也已统一弹出提示，
因此业务代码用 `try/catch` 包住即可，`catch` 里通常留空注释。

### 分页规范

分页接口统一返回 `{ total, page, page_size, items }`，请求参数统一为
`{ page, page_size, ...筛选条件 }`。列表页请使用 `el-pagination`：

```vue
<div class="pagination-bar">
  <el-pagination
    v-model:current-page="query.page"
    v-model:page-size="query.page_size"
    :total="total"
    :page-sizes="[10, 20, 50, 100]"
    layout="total, sizes, prev, pager, next, jumper"
    background
    @size-change="load"
    @current-change="load"
  />
</div>
```

## 5. 后端接口与数据结构（严格按此对接）

### 5.1 运营区域 `regionApi`

- `all()` → `[{ id, code, name, region_type, center_lng, center_lat, area_km2, demand_level, status }]`
- `page({ page, page_size, keyword, region_type, status })` → 分页结构
- `types()` → `["交通枢纽","商圈",...]`
- `create(data)` / `update(id, data)` / `remove(id)`
- 提交字段：`{ code, name, region_type, center_lng, center_lat, area_km2, demand_level, status, remark }`
- 删除有关联数据的区域会返回 400，需要提示用户改为「停用」。

### 5.2 车辆 `vehicleApi`

- `page({ page, page_size, keyword, status, home_region_id, vehicle_type, energy_type, expiring })`
- `all()` → 全部在营车辆数组
- `dictionaries()` → `{ vehicle_type: [], energy_type: [], status: [{value,label}] }`
- 记录字段：`id, plate_number, brand_model, color, vehicle_type, energy_type, seats,
  purchase_date, purchase_price, mileage_total, insurance_expire, cert_expire,
  next_maintenance_date, maintenance_cycle_days, home_region_id, home_region_name,
  status, remark, bound_driver_id, bound_driver_name, order_count, total_income`
- `updateStatus(id, status)`；`create/update` 提交 `VehicleBase` 字段
- 状态字典：`{ 0: '停运', 1: '在营', 2: '维修' }`（用 `VEHICLE_STATUS`）

### 5.3 驾驶员 `driverApi`

- `page({ page, page_size, keyword, status, home_region_id, expiring })`
- 记录字段：`id, name, gender(M/F), id_card, license_no, qualification_no, phone, birth_date,
  hire_date, license_expire, rating, complaint_count, violation_count, home_region_id,
  home_region_name, status, bound_vehicle_id, bound_plate, order_count, total_income`
- 状态字典用 `DRIVER_STATUS`。`create/update` 提交 `DriverBase` 字段。

### 5.4 人车绑定 `assignmentApi`

- `page({ page, page_size, vehicle_id, driver_id, status })`
- 记录字段：`id, vehicle_id, driver_id, assign_date, unassign_date, shift, status,
  remark, plate_number, driver_name, driver_phone`
- `create({ vehicle_id, driver_id, assign_date, shift, remark })`，`shift` ∈ `白班/夜班/全天`
- `remove(id)` 为「解绑」（仅结束绑定，保留历史）。同一车辆同一班次最多 2 人，超出返回 400。

### 5.5 营运订单 `operationApi`

- `page({ page, page_size, start_date, end_date, vehicle_id, driver_id, region_id,
   keyword, pay_type, peak, min_amount, max_amount })`
- `summary(同筛选条件)` → `{ order_count, total_income, loaded_mileage, empty_mileage, avg_amount, empty_rate }`
- 记录字段：`id, order_no, vehicle_id, driver_id, pickup_region_id, dropoff_region_id,
  start_time, end_time, stat_date, hour, weekday, loaded_mileage, empty_mileage, amount,
  duration_minutes, avg_speed, passenger_count, pay_type, weather, is_peak,
  plate_number, driver_name, pickup_region_name, dropoff_region_name`
- `payTypes()` → 字符串数组
- `create(data)`：`{ order_no(可空), vehicle_id, driver_id, pickup_region_id, dropoff_region_id,
   start_time, end_time, loaded_mileage, empty_mileage, amount, passenger_count, pay_type, weather }`
   （`start_time` 用 `value-format="YYYY-MM-DD HH:mm:ss"`）
- `update(id, data)` / `remove(id)`
- 导入：`importExcel(formData)` → `{ success, total_rows, imported, duplicated, error_rows: [], error_messages: [] }`
- 模板下载：`operationApi.templateUrl`（字符串 URL，需带 token 下载 → 用 `downloadWithAuth`）
- 导出：`operationApi.exportUrl({ fmt:'csv'|'xlsx', ...筛选条件 })` + `downloadWithAuth(url, 文件名)`

### 5.6 叫车需求 `demandApi`

- `page({ page, page_size, start_date, end_date, region_id, status, hour, weather })`
- 记录字段：`id, request_no, region_id, region_name, request_time, stat_date, hour, weekday,
  passenger_count, status, status_text, wait_seconds, is_peak, weather, is_holiday, order_no`
- `status`：`0 无人接单 / 1 已接单 / 2 已完成 / 3 已取消`（用 `REQUEST_STATUS`）
- `summary({ start_date, end_date, region_id })` → `{ start, end, request_count, fulfilled_count,
  unfulfilled_count, fulfil_rate, avg_wait_seconds, passenger_count, avg_daily }`
- `regionHourMatrix({ start_date, end_date })` → `{ y_labels: [], x_labels: [], matrix: [[]], days }`
- `weekdayHour({ start_date, end_date, region_id })` → `{ x_labels: [], y_labels: [周一..周日], matrix: [[7×24]] }`

### 5.7 运营分析 `analysisApi`

| 方法 | 参数 | 返回 |
| --- | --- | --- |
| `overview({start_date,end_date})` | | KPI 对象，见下 |
| `incomeTrend({start_date,end_date,group_by})` | group_by: hour/day/week/month | `[{ period, order_count, income, avg_amount, empty_rate }]` |
| `hourlyProfile({start_date,end_date})` | | `[{ hour, hour_label, demand, supply, income, unfulfilled, fulfil_rate, is_peak }]`（24 条） |
| `weekdayProfile({start_date,end_date})` | | `[{ weekday, weekday_label, demand, supply, income, is_weekend }]`（7 条） |
| `heatmap({start_date,end_date})` | | `{ x_labels, y_labels, data:[[x,y,v]], matrix, max_value, min_value }` |
| `regionRanking({start_date,end_date})` | | `[{ region_id, region_name, region_type, demand_level, demand, order_count, income, unfulfilled, unfulfil_rate, empty_rate, avg_amount }]` |
| `regionCompare({start_date,end_date,region_ids})` | region_ids 逗号分隔 | `{ indicators:[{name,max}], series:[{name,value:[],raw:{}}] }` 雷达图 |
| `loadRate({start_date,end_date,vehicle_id,region_id})` | | `{ loaded_mileage, empty_mileage, total_mileage, load_rate, empty_rate, order_count }` |
| `driverRanking({start_date,end_date,top_n,sort_by})` | sort_by: income/order_count/score/rating | `[{ driver_id, name, rating, status, order_count, income, loaded_mileage, empty_rate, avg_amount, score }]` |
| `vehicleEfficiency({start_date,end_date,top_n,order})` | order: asc/desc | `[{ vehicle_id, plate_number, brand_model, status, status_text, order_count, income, total_mileage, empty_rate, income_per_km }]` |
| `payType({start_date,end_date})` | | `[{ pay_type, order_count, income, ratio }]` |
| `weatherImpact({start_date,end_date})` | | `[{ weather, demand, supply, income, avg_amount, fulfil_rate }]` |
| `abnormalAlert({days})` | | `[{ level(high/medium/low), type, target, title, content, value, unit, suggestion }]` |
| `dashboard({start_date,end_date})` | | `{ range, kpi, income_trend, hourly, weekday, regions, pay_types, driver_top, vehicle_top }` |

`overview` 返回的 KPI 字段：
`start, end, order_count, income, loaded_mileage, empty_mileage, total_mileage, empty_rate,
avg_amount, avg_distance, avg_duration, active_vehicles, active_drivers, income_per_vehicle,
orders_per_vehicle, request_count, fulfilled_count, fulfil_rate, avg_wait_seconds,
peak_income, peak_income_ratio, span_days, prev_period, vs_prev{order_count,income,empty_rate,fulfil_rate,avg_amount,request_count}`

### 5.8 需求预测 `forecastApi`

- `models()` → `[{ value, label }]`（value: `mean_baseline/seasonal_naive/moving_average/holt_winters/linear_regression/ensemble`）
- `regions()` → `[{ region_id(可为 null 表示全域), region_name, region_type, request_count }]`
- `run({ region_id, horizon, models, auto_select })` → 预测结果对象，见下
- `quick({ region_id, horizon })` → 同上
- `accuracy({ days })` → `[{ model_label, sample_count, mae, rmse, mape, accuracy }]`
- `history({ limit })` → `[{ batch_no, model, model_label, region_id, region_name, horizon, mape, create_time, point_count, start_time, end_time }]`
- `batch(batchNo)` → `[{ target_time, predicted_value, lower_bound, upper_bound, actual_value }]`

`run` / `quick` 返回：

```js
{
  region_id, region_name, model, model_label, horizon, history_days,
  generated_at, batch_no, select_metric, folds, valid_hours,
  metrics: [{ model, model_label, mae, rmse, mape, r2, is_best }],   // mape 可能为 null
  points:  [{ time, value, lower, upper }],                          // 未来 horizon 小时
  history: [{ time, value, lower, upper }]                           // 最近 7 天实际值
}
```

预测耗时较长（数秒），按钮需要 `:loading`，并给用户文字提示。

### 5.9 调度决策 `dispatchApi`

- `regionStatus({ target_date, target_hour })` → `{ target_date, target_hour, auto_selected, method,
  items: [{ region_id, region_name, region_type, predicted_demand, current_supply, effective_supply,
  gap, gap_level, expected_revenue }] }`
  （`gap > 0` 为缺口区域，`gap < 0` 为盈余区域；`gap_level` 取值：严重缺口/明显缺口/轻微缺口/运力盈余）
- `generate({ plan_date, target_hour, strategy, auto_save })` → `{ plan, region_status, strategy_compare, warnings }`
  - `strategy` ∈ `greedy` | `hungarian`
  - `plan` 结构同方案对象（见下），含 `orders: []`
  - `strategy_compare` → `[{ strategy, strategy_label, dispatch_count, expected_gain }]`
  - `warnings` → 字符串数组（务必展示，含「自动选择时段」等说明）
- `plans({ page, page_size, start_date, end_date, status })` → 分页；条目字段：
  `id, plan_no, plan_date, target_hour, strategy, forecast_model, total_demand, total_supply,
   total_gap, dispatch_count, expected_gain, status, status_text, remark, created_by,
   create_time, done_count`
- `planDetail(id)` → 同上并含 `orders: [...]`
- 调度单字段：`id, plan_id, dispatch_no, vehicle_id, driver_id, from_region_id, to_region_id,
  start_hour, end_hour, predicted_demand, predicted_supply, gap, distance_km, expected_revenue,
  expected_cost, expected_gain, priority(1/2/3), status, status_text, executed_time, feedback,
  plate_number, driver_name, from_region_name, to_region_name`
- `orders({ page, page_size, plan_id, status, to_region_id })` → 分页
- `feedback(id, { status, feedback })` → `status` ∈ `1 执行中 / 2 已完成 / 3 已拒绝 / 4 已取消`
- `effect(id)` → `{ plan_id, plan_no, dispatch_count, done_count, done_ratio, expected_gain,
  actual_gain, accuracy, detail: [{ dispatch_no, to_region_name, status, expected_gain,
  actual_income, baseline_income, actual_gain, distance_km }] }`
- `strategyCompare({ hours })` → `{ hours, evaluated_hours, start, rows: [{ time, hour,
  deficit_regions, surplus_regions, total_gap, greedy_count, greedy_gain, hungarian_count,
  hungarian_gain, improve, improve_pct }], totals: { greedy: {...}, hungarian: {...} },
  improve, improve_pct, better_hours, tie_hours }`
- `strategyBenchmark({ instances })` → `{ seed, cost_per_km, results: [{ size, instances,
  greedy_mean_gain, hungarian_mean_gain, mean_improve, improve_pct,
  hungarian_better_instances, tie_instances, better_ratio, greedy_avg_ms, hungarian_avg_ms }] }`
- `statistics({ days })` → `{ days, plan_count, order_count, expected_gain, done_count,
  rejected_count, pending_count, done_ratio, by_status: [{status,status_text,count}],
  by_strategy: [{strategy,plan_count,dispatch_count,expected_gain}], daily: [...] }`
- `updatePlanStatus(id, status)` / `removePlan(id)`

方案状态 `PLAN_STATUS`：`0 草稿 / 1 已下发 / 2 执行中 / 3 已完成 / 4 已取消`
调度单状态 `DISPATCH_STATUS`：`0 待执行 / 1 执行中 / 2 已完成 / 3 已拒绝 / 4 已取消`

### 5.10 系统管理 `systemApi`

- `users({ page, page_size, keyword, role })` → 分页，字段 `{ id, username, real_name, role, phone, status, last_login, create_time }`
- `createUser({ username, password, real_name, role, phone })`、`updateUser(id, { real_name, role, phone, status })`
- `resetPassword(id, { new_password })`、`removeUser(id)`
- `configs()` → `[{ id, config_key, config_value, config_name, config_group, value_type, description, update_time }]`
- `updateConfig(key, value)`（value 为字符串）、`reloadConfigs()`
- `logs({ page, page_size, keyword, module, days })` → 分页，字段 `{ id, username, module, operation, method, path, ip, status_code, cost_ms, create_time }`
- `clearLogs({ days })`
- `dataStats()` → `{ region, vehicle, driver, vehicle_driver, ride_request, operation_record, dispatch_plan, dispatch_order, forecast_result, sys_user, operation_log }`
- `simulate({ days, vehicles, drivers, seed, reset })` → `{ message, regions, vehicles, drivers, bindings, requests, operations, seconds }`
  ⚠️ 耗时约 1~3 分钟，必须二次确认 + loading 提示
- `clearData({ include_master })`

### 5.11 驾驶舱 `dashboardApi`

- `summary()` → `{ today: {...KPI 字段, vs_yesterday:{...}}, week: {...}, fleet: { vehicle_total,
  vehicle_active, vehicle_idle, vehicle_repair, driver_total, driver_active, driver_leave,
  driver_rest }, realtime: { window_hours, demand, supply, fulfil_rate }, pending_dispatch, updated_at }`
- `trend({ days })` → `{ range, income: [...], hourly: [...], regions: [...] }`
- `alerts({ limit, days })` → `{ total, items: [{ level, type, target, title, content, value, unit, suggestion }] }`
- `health()` → `{ counts: {...}, latest_request_time, latest_order_time, history_days, ready_for_forecast }`

### 5.12 认证 `authApi`

- `login({ username, password })` → `{ access_token, token_type, expires_in }`
- `me()` → `{ id, username, real_name, role, phone, status, last_login }`
- `changePassword({ old_password, new_password })`
- `logout()`

## 6. 工具函数（`src/utils/format.js`）

`thousands(v, digits)`、`money(v, digits)`、`moneyShort(v)`、`percent(v, digits)`、
`changeInfo(v, inverse)`、`duration(seconds)`、`formatDateTime(v, withSeconds)`、
`formatDate(v)`、`recentRange(days)` → `[start, end]`、`hourLabel(h)`、
`download(url, filename)`、`downloadWithAuth(url, filename)`、
字典：`WEEKDAYS`、`VEHICLE_STATUS`、`DRIVER_STATUS`、`REQUEST_STATUS`、
`DISPATCH_STATUS`、`PLAN_STATUS`、`ROLE_TEXT`。

## 7. 交互与文案要求

- 全部界面文案使用**简体中文**，术语与后端保持一致（营运订单、叫车需求、供需缺口、净收益等）。
- 危险操作（删除、清空、重新生成数据）必须 `ElMessageBox.confirm` 二次确认。
- 保存成功用 `ElMessage.success`；失败由拦截器统一提示，业务代码不要再弹错误。
- 每个图表卡片下方如需要，可用 `chart-card__desc` 写一句**业务解释**，
  例如「满足率 = 实际完成订单 / 叫车需求，低于 80% 说明运力不足」。
- 空数据时图表要能正常显示空态（ChartBox 已内置 `empty` 属性）。
- 页面在 1366×768 下不应出现横向滚动条；表格列过多时设置 `width` 并允许横向滚动。
- 表格数值列建议加 `align="right"`，状态列用 `el-tag`。
