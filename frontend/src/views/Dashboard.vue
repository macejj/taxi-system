<template>
  <div v-loading="loading">
    <PageHeader
      title="运营驾驶舱"
      description="实时掌握车队运营状况、供需态势与风险预警，数据每 60 秒自动刷新。"
    >
      <template #extra>
        <el-tag type="info" effect="plain">
          <el-icon><Timer /></el-icon>
          更新于 {{ updatedAt }}
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 今日核心指标 -->
    <el-row :gutter="14">
      <el-col v-for="card in kpiCards" :key="card.label" :xs="12" :sm="12" :md="6" :lg="6">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 车队与实时概况 -->
    <el-row :gutter="14" class="mb-16">
      <el-col :xs="24" :md="8">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">车队概况</div>
            <el-button link type="primary" @click="$router.push('/vehicles')">车辆管理</el-button>
          </div>
          <div class="fleet-grid">
            <div v-for="item in fleetItems" :key="item.label" class="fleet-grid__item">
              <div class="fleet-grid__value" :class="item.class">{{ item.value }}</div>
              <div class="fleet-grid__label">{{ item.label }}</div>
            </div>
          </div>
          <el-divider style="margin: 12px 0" />
          <div class="realtime-row">
            <span class="text-muted">近 6 小时</span>
            <span>需求 <b>{{ realtime.demand || 0 }}</b> 单</span>
            <span>完成 <b>{{ realtime.supply || 0 }}</b> 单</span>
            <el-tag :type="realtimeTagType" size="small" effect="light">
              满足率 {{ realtime.fulfil_rate ?? 0 }}%
            </el-tag>
          </div>
          <div v-if="summary.pending_dispatch" class="mt-16">
            <el-alert
              :title="`当前有 ${summary.pending_dispatch} 条调度指令待执行`"
              type="warning"
              :closable="false"
              show-icon
            >
              <template #default>
                <el-button link type="primary" @click="$router.push('/dispatch')">
                  前往调度中心处理
                </el-button>
              </template>
            </el-alert>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="16">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">近 {{ trendDays }} 天收入与订单趋势</div>
            <el-radio-group v-model="trendDays" size="small" @change="loadTrend">
              <el-radio-button :value="7">7 天</el-radio-button>
              <el-radio-button :value="14">14 天</el-radio-button>
              <el-radio-button :value="30">30 天</el-radio-button>
            </el-radio-group>
          </div>
          <ChartBox :option="trendOption" :height="280" :loading="loading" :empty="!trend.income?.length" />
        </div>
      </el-col>
    </el-row>

    <!-- 时段分布 + 区域排行 -->
    <el-row :gutter="14" class="mb-16">
      <el-col :xs="24" :md="14">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">24 小时需求与运力匹配</div>
            <span class="text-muted" style="font-size: 12px">柱=叫车需求，折线=实际完成</span>
          </div>
          <ChartBox :option="hourlyOption" :height="300" :loading="loading" />
        </div>
      </el-col>
      <el-col :xs="24" :md="10">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">区域收入排行 TOP8</div>
            <el-button link type="primary" @click="$router.push('/analysis')">更多分析</el-button>
          </div>
          <ChartBox :option="regionOption" :height="300" :loading="loading" />
        </div>
      </el-col>
    </el-row>

    <!-- 预警 + 待办 -->
    <el-row :gutter="14">
      <el-col :xs="24" :md="14">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">
              运营预警
              <el-tag v-if="alertTotal" type="danger" size="small" effect="dark">
                {{ alertTotal }}
              </el-tag>
            </div>
            <el-radio-group v-model="alertFilter" size="small">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="high">高优先级</el-radio-button>
            </el-radio-group>
          </div>
          <el-scrollbar height="300px">
            <el-empty v-if="!filteredAlerts.length" description="暂无预警，运营状况良好" :image-size="70" />
            <div
              v-for="(item, index) in filteredAlerts"
              :key="index"
              class="alert-item"
              :class="`alert-item--${item.level}`"
            >
              <el-tag :type="levelTag(item.level)" size="small" effect="dark">
                {{ levelText(item.level) }}
              </el-tag>
              <div class="alert-item__body">
                <div class="alert-item__title">{{ item.title }}</div>
                <div class="alert-item__content">{{ item.content }}</div>
                <div class="alert-item__suggestion">
                  <el-icon><InfoFilled /></el-icon>{{ item.suggestion }}
                </div>
              </div>
              <el-tag size="small" type="info" effect="plain">{{ item.type }}</el-tag>
            </div>
          </el-scrollbar>
        </div>
      </el-col>

      <el-col :xs="24" :md="10">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">快捷入口</div>
          </div>
          <div class="shortcut-grid">
            <div
              v-for="item in shortcuts"
              :key="item.path"
              class="shortcut"
              @click="$router.push(item.path)"
            >
              <el-icon :size="22"><component :is="item.icon" /></el-icon>
              <div class="shortcut__title">{{ item.title }}</div>
              <div class="shortcut__desc">{{ item.desc }}</div>
            </div>
          </div>

          <el-divider style="margin: 14px 0" />
          <div class="chart-card__head">
            <div class="chart-card__title">数据健康度</div>
            <el-tag :type="health.ready_for_forecast ? 'success' : 'warning'" size="small">
              {{ health.ready_for_forecast ? '可建模' : '数据不足' }}
            </el-tag>
          </div>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="运营区域">{{ health.counts?.region || 0 }}</el-descriptions-item>
            <el-descriptions-item label="车辆">{{ health.counts?.vehicle || 0 }}</el-descriptions-item>
            <el-descriptions-item label="驾驶员">{{ health.counts?.driver || 0 }}</el-descriptions-item>
            <el-descriptions-item label="历史天数">{{ health.history_days || 0 }}</el-descriptions-item>
            <el-descriptions-item label="叫车需求">{{ thousands(health.counts?.ride_request) }}</el-descriptions-item>
            <el-descriptions-item label="营运订单">{{ thousands(health.counts?.operation_record) }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { Refresh, Timer } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import ChartBox from '../components/ChartBox.vue';
import { dashboardApi, analysisApi } from '../api';
import { formatDateTime, thousands } from '../utils/format';

const loading = ref(false);
const summary = ref({});
const trend = ref({ income: [], hourly: [], regions: [] });
const alerts = ref([]);
const alertTotal = ref(0);
const health = ref({});
const trendDays = ref(14);
const alertFilter = ref('all');
const updatedAt = ref('-');
let timer = null;

const kpiCards = computed(() => {
  const today = summary.value.today || {};
  const vs = today.vs_yesterday || {};
  const fleet = summary.value.fleet || {};
  return [
    {
      label: '今日订单量',
      value: today.order_count ?? 0,
      unit: '单',
      icon: 'Tickets',
      tone: 'blue',
      change: vs.order_count,
      changeLabel: '较昨日',
      sub: `活跃车辆 ${today.active_vehicles ?? 0} 台`,
    },
    {
      label: '今日总收入',
      value: today.income ?? 0,
      unit: '元',
      icon: 'Money',
      tone: 'green',
      digits: 2,
      change: vs.income,
      changeLabel: '较昨日',
      sub: `单均 ${today.avg_amount ?? 0} 元`,
    },
    {
      label: '今日需求满足率',
      value: today.fulfil_rate ?? 0,
      unit: '%',
      icon: 'CircleCheck',
      tone: 'cyan',
      digits: 1,
      change: vs.fulfil_rate,
      changeLabel: '较昨日',
      sub: `叫车 ${today.request_count ?? 0} 单 / 未满足 ${Math.max(
        0,
        (today.request_count ?? 0) - (today.fulfilled_count ?? 0)
      )} 单`,
    },
    {
      label: '今日空驶率',
      value: today.empty_rate ?? 0,
      unit: '%',
      icon: 'Odometer',
      tone: 'orange',
      digits: 1,
      change: vs.empty_rate,
      changeLabel: '较昨日',
      inverse: true,
      sub: `在营车辆 ${fleet.vehicle_active ?? 0} 台 / 停运 ${fleet.vehicle_idle ?? 0} 台`,
    },
  ];
});

const fleetItems = computed(() => {
  const fleet = summary.value.fleet || {};
  return [
    { label: '在营车辆', value: fleet.vehicle_active ?? 0, class: 'text-success' },
    { label: '停运/维修', value: (fleet.vehicle_idle ?? 0) + (fleet.vehicle_repair ?? 0), class: 'text-danger' },
    { label: '在职驾驶员', value: fleet.driver_active ?? 0, class: 'text-success' },
    { label: '离职/休假', value: (fleet.driver_leave ?? 0) + (fleet.driver_rest ?? 0), class: 'text-warning' },
  ];
});

const realtime = computed(() => summary.value.realtime || {});
const realtimeTagType = computed(() => {
  const rate = realtime.value.fulfil_rate ?? 100;
  if (rate >= 90) return 'success';
  if (rate >= 75) return 'warning';
  return 'danger';
});

const filteredAlerts = computed(() =>
  alertFilter.value === 'high' ? alerts.value.filter((item) => item.level === 'high') : alerts.value
);

const shortcuts = [
  { path: '/forecast', title: '需求预测', desc: '预测未来 24 小时逐时需求', icon: 'MagicStick' },
  { path: '/dispatch', title: '调度决策', desc: '测算供需缺口并生成调度方案', icon: 'Guide' },
  { path: '/operations', title: '营运订单', desc: '查询、导入与导出运营数据', icon: 'Tickets' },
  { path: '/demand', title: '需求分析', desc: '时段、区域与天气需求分布', icon: 'DataLine' },
];

const trendOption = computed(() => {
  const list = trend.value.income || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['收入(元)', '订单量'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: list.map((item) => item.period),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: [
      {
        type: 'value',
        name: '收入(元)',
        splitLine: { lineStyle: { color: '#f1f4f9' } },
        axisLabel: { color: '#6b7280' },
      },
      {
        type: 'value',
        name: '订单量',
        splitLine: { show: false },
        axisLabel: { color: '#6b7280' },
      },
    ],
    series: [
      {
        name: '收入(元)',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.income),
        itemStyle: { color: '#2b6de5' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(43,109,229,0.28)' },
              { offset: 1, color: 'rgba(43,109,229,0.02)' },
            ],
          },
        },
      },
      {
        name: '订单量',
        type: 'bar',
        yAxisIndex: 1,
        barWidth: '42%',
        data: list.map((item) => item.order_count),
        itemStyle: { color: 'rgba(6,182,212,0.55)', borderRadius: [4, 4, 0, 0] },
      },
    ],
  };
});

const hourlyOption = computed(() => {
  const list = trend.value.hourly || [];
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['叫车需求', '实际完成', '满足率'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.hour_label),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280', interval: 1 },
    },
    yAxis: [
      { type: 'value', name: '订单数', splitLine: { lineStyle: { color: '#f1f4f9' } } },
      { type: 'value', name: '满足率(%)', max: 100, splitLine: { show: false } },
    ],
    series: [
      {
        name: '叫车需求',
        type: 'bar',
        data: list.map((item) => item.demand),
        itemStyle: { color: 'rgba(43,109,229,0.75)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '实际完成',
        type: 'bar',
        data: list.map((item) => item.supply),
        itemStyle: { color: 'rgba(16,185,129,0.8)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '满足率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 5,
        data: list.map((item) => item.fulfil_rate),
        itemStyle: { color: '#f59e0b' },
      },
    ],
  };
});

const regionOption = computed(() => {
  const list = [...(trend.value.regions || [])].reverse();
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const item = list[params[0].dataIndex];
        return `${item.region_name}<br/>收入：${thousands(item.income, 2)} 元<br/>订单：${item.order_count} 单<br/>未满足率：${item.unfulfil_rate}%`;
      },
    },
    grid: { left: 10, right: 40, top: 14, bottom: 6, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f4f9' } } },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.region_name),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#4b5563' },
    },
    series: [
      {
        type: 'bar',
        barWidth: 14,
        data: list.map((item) => item.income),
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#7dd3fc' },
              { offset: 1, color: '#2b6de5' },
            ],
          },
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params) => thousands(params.value, 0),
          color: '#6b7280',
          fontSize: 11,
        },
      },
    ],
  };
});

function levelTag(level) {
  return { high: 'danger', medium: 'warning', low: 'info' }[level] || 'info';
}
function levelText(level) {
  return { high: '高', medium: '中', low: '低' }[level] || '低';
}

async function loadSummary() {
  summary.value = await dashboardApi.summary();
}

async function loadTrend() {
  trend.value = await dashboardApi.trend({ days: trendDays.value });
}

async function loadAlerts() {
  const data = await dashboardApi.alerts({ limit: 30, days: 7 });
  alerts.value = data.items || [];
  alertTotal.value = data.total || 0;
}

async function loadHealth() {
  health.value = await dashboardApi.health();
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadSummary(), loadTrend(), loadAlerts(), loadHealth()]);
    updatedAt.value = formatDateTime(new Date(), true).slice(11);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAll();
  timer = setInterval(loadAll, 60000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.fleet-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.fleet-grid__item {
  background: #f7f9fc;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.fleet-grid__value {
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.fleet-grid__label {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 2px;
}
.realtime-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 13px;
  flex-wrap: wrap;
}
.realtime-row b {
  color: var(--app-primary);
}
.alert-item {
  display: flex;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 8px;
  background: #fafbfd;
  border-left: 3px solid #cbd5e1;
  margin-bottom: 8px;
  align-items: flex-start;
}
.alert-item--high {
  border-left-color: #ef4444;
  background: #fef4f4;
}
.alert-item--medium {
  border-left-color: #f59e0b;
  background: #fffaf0;
}
.alert-item--low {
  border-left-color: #94a3b8;
}
.alert-item__body {
  flex: 1;
  min-width: 0;
}
.alert-item__title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--app-text);
}
.alert-item__content {
  font-size: 12.5px;
  color: var(--app-text-secondary);
  margin-top: 3px;
  line-height: 1.6;
}
.alert-item__suggestion {
  font-size: 12px;
  color: #2b6de5;
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.shortcut {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--app-primary);
}
.shortcut:hover {
  border-color: var(--app-primary);
  background: #f5f9ff;
  transform: translateY(-1px);
}
.shortcut__title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--app-text);
  margin-top: 6px;
}
.shortcut__desc {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 3px;
  line-height: 1.5;
}
</style>
