<template>
  <div v-loading="loading">
    <PageHeader
      title="叫车需求分析"
      description="数据来源为乘客叫车请求（需求侧数据，含未被满足的需求），与已完成的营运订单不同；本页从时段、区域、星期与天气四个维度刻画需求分布，是需求预测与调度决策的输入依据。"
    >
      <template #extra>
        <el-tag type="warning" effect="plain">
          <el-icon><Bell /></el-icon>
          未满足 {{ thousands(summary.unfulfilled_count) }} 单
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="日期区间">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            :clearable="false"
            style="width: 250px"
            @change="loadAll"
          />
        </el-form-item>
        <el-form-item label="运营区域">
          <el-select
            v-model="regionId"
            placeholder="全部区域"
            clearable
            filterable
            style="width: 180px"
            @change="loadAll"
          >
            <el-option label="全部区域" :value="null" />
            <el-option
              v-for="item in regions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="loadAll">查询</el-button>
          <el-button :icon="RefreshLeft" @click="reset">重置</el-button>
          <span class="text-muted" style="font-size: 12px; margin-left: 6px">
            区域筛选作用于汇总卡与区域需求排行表
          </span>
        </el-form-item>
      </el-form>
    </div>

    <!-- 需求汇总 -->
    <el-row :gutter="14">
      <el-col v-for="card in summaryCards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 时段需求与满足率 -->
    <div class="chart-card mb-16">
      <div class="chart-card__head">
        <div class="chart-card__title">24 小时叫车需求与满足情况</div>
        <span class="text-muted" style="font-size: 12px">柱=叫车需求/实际完成，折线=满足率</span>
      </div>
      <div class="chart-card__desc">
        需求指乘客发起的叫车请求，实际完成为对应的营运订单；满足率 = 实际完成 / 叫车需求，
        低于 80% 说明该时段运力不足，调度时应优先向该时段倾斜。
      </div>
      <ChartBox :option="hourlyOption" :height="320" :loading="loading" :empty="!hourly.length" />
    </div>

    <el-row :gutter="14">
      <el-col :xs="24" :lg="14">
        <div class="chart-card mb-16">
          <div class="chart-card__head">
            <div class="chart-card__title">星期 × 小时需求热力图</div>
            <span class="text-muted" style="font-size: 12px">单位：单/小时</span>
          </div>
          <div class="chart-card__desc">
            行=周一至周日，列=0-23 时，颜色越深代表该「星期 + 时段」的叫车需求越集中，
            可用于排班与运力预置（跨星期取日均口径）。
          </div>
          <ChartBox :option="heatmapOption" :height="330" :loading="loading" :empty="!heatmapData.length" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="chart-card mb-16">
          <div class="chart-card__head">
            <div class="chart-card__title">区域需求排行 TOP10</div>
            <span class="text-muted" style="font-size: 12px">按叫车需求降序</span>
          </div>
          <div class="chart-card__desc">
            对比各区域的叫车需求、实际完成与未满足率（排行表可按区域筛选）；
            未满足率高于 15% 的区域存在明显供需缺口。
          </div>
          <ChartBox :option="regionOption" :height="330" :loading="loading" :empty="!regionRank.length" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="14">
      <el-col :xs="24" :lg="14">
        <div class="chart-card mb-16">
          <div class="chart-card__head">
            <div class="chart-card__title">区域 × 时段日均需求（单/小时）</div>
            <span class="text-muted" style="font-size: 12px">
              共 {{ regionMatrix.days || 0 }} 天
            </span>
          </div>
          <div class="chart-card__desc">
            每个区域一行、每个小时一列，单元格数值为该区域在该小时的日均叫车需求；
            颜色越深说明需求越旺盛，是区域级调度与车辆投放的直接依据。
          </div>
          <ChartBox
            :option="matrixOption"
            :height="matrixHeight"
            :loading="loading"
            :empty="!matrixData.length"
          />
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="chart-card mb-16">
          <div class="chart-card__head">
            <div class="chart-card__title">周一至周日需求分布</div>
            <span class="text-muted" style="font-size: 12px">工作日与周末差异</span>
          </div>
          <div class="chart-card__desc">
            需求为区间内各星期的叫车请求合计，完成为对应的营运订单；
            周末需求高峰时段通常晚于工作日。
          </div>
          <ChartBox :option="weekdayOption" :height="300" :loading="loading" :empty="!weekday.length" />
        </div>
      </el-col>
    </el-row>

    <div class="chart-card mb-16">
      <div class="chart-card__head">
        <div class="chart-card__title">天气对需求与满足率的影响</div>
        <span class="text-muted" style="font-size: 12px">柱=订单量，折线=满足率</span>
      </div>
      <div class="chart-card__desc">
        雨雪等恶劣天气通常推高叫车需求，同时降低运力周转效率，
        满足率随之下降；应提前准备天气预案与运力储备。
      </div>
      <ChartBox :option="weatherOption" :height="300" :loading="loading" :empty="!weather.length" />
    </div>

    <!-- 区域需求排行明细 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div class="chart-card__title">区域需求排行明细</div>
        <span class="text-muted" style="font-size: 12px">
          未满足率高于 15% 的区域需要重点补充运力
        </span>
      </div>
      <el-table :data="regionRank" border stripe style="width: 100%">
        <el-table-column type="index" label="#" width="55" align="center" />
        <el-table-column prop="region_name" label="区域" min-width="140" />
        <el-table-column prop="region_type" label="功能区" width="110" />
        <el-table-column label="需求强度" width="110">
          <template #default="{ row }">
            <el-rate
              :model-value="Number(row.demand_level) || 0"
              disabled
              :max="5"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column label="叫车需求" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.demand) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="实际完成" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.order_count) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="未满足" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="row.unfulfilled ? 'text-danger' : ''">
              {{ thousands(row.unfulfilled) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="未满足率" width="120" align="right">
          <template #default="{ row }">
            <el-tag
              :type="row.unfulfil_rate > 15 ? 'danger' : 'success'"
              size="small"
              effect="light"
            >
              {{ percent(row.unfulfil_rate) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="单均收入" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ money(row.avg_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="空驶率" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ percent(row.empty_rate) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="所选区间内暂无区域需求数据" :image-size="80" />
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { Bell, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import ChartBox from '../components/ChartBox.vue';
import { analysisApi, demandApi, regionApi } from '../api';
import { duration, money, percent, recentRange, thousands } from '../utils/format';

const loading = ref(false);
const dateRange = ref(recentRange(14));
const regionId = ref(null);
const regions = ref([]);
const summary = ref({});
const hourly = ref([]);
const heatmap = ref({});
const regionRank = ref([]);
const regionMatrix = ref({});
const weekday = ref([]);
const weather = ref([]);

const rangeParams = computed(() => ({
  start_date: dateRange.value?.[0] || undefined,
  end_date: dateRange.value?.[1] || undefined,
}));

const summaryCards = computed(() => {
  const data = summary.value || {};
  return [
    {
      label: '叫车需求总量',
      value: data.request_count ?? 0,
      unit: '单',
      icon: 'Bell',
      tone: 'blue',
      sub: `统计区间 ${data.start || '-'} 至 ${data.end || '-'}`,
    },
    {
      label: '已完成需求',
      value: data.fulfilled_count ?? 0,
      unit: '单',
      icon: 'CircleCheck',
      tone: 'green',
      sub: `乘客人数 ${thousands(data.passenger_count)} 人`,
    },
    {
      label: '未满足需求',
      value: data.unfulfilled_count ?? 0,
      unit: '单',
      icon: 'WarningFilled',
      tone: 'red',
      sub: '含无人接单与乘客取消',
    },
    {
      label: '需求满足率',
      value: data.fulfil_rate ?? 0,
      unit: '%',
      icon: 'DataLine',
      tone: 'cyan',
      digits: 1,
      sub: '低于 80% 说明运力不足',
    },
    {
      label: '平均等待时长',
      value: duration(data.avg_wait_seconds),
      icon: 'Timer',
      tone: 'orange',
      sub: '乘客发起叫车到上车的时间',
    },
    {
      label: '日均需求',
      value: data.avg_daily ?? 0,
      unit: '单/天',
      icon: 'TrendCharts',
      tone: 'purple',
      digits: 1,
    },
  ];
});

/* --------------------------------------------------------------- 图表 1 */
const hourlyOption = computed(() => {
  const list = hourly.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['叫车需求', '实际完成', '满足率'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 44, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.hour_label),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280', interval: 1 },
    },
    yAxis: [
      {
        type: 'value',
        name: '订单数',
        splitLine: { lineStyle: { color: '#f1f4f9' } },
        axisLabel: { color: '#6b7280' },
      },
      {
        type: 'value',
        name: '满足率(%)',
        max: 100,
        splitLine: { show: false },
        axisLabel: { color: '#6b7280', formatter: '{value}' },
      },
    ],
    series: [
      {
        name: '叫车需求',
        type: 'bar',
        barMaxWidth: 16,
        data: list.map((item) => item.demand ?? 0),
        itemStyle: { color: 'rgba(43,109,229,0.78)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '实际完成',
        type: 'bar',
        barMaxWidth: 16,
        data: list.map((item) => item.supply ?? 0),
        itemStyle: { color: 'rgba(16,185,129,0.8)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '满足率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 5,
        data: list.map((item) => item.fulfil_rate ?? 0),
        itemStyle: { color: '#f59e0b' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#ef4444', type: 'dashed' },
          label: { formatter: '80% 运力警戒线', color: '#ef4444', fontSize: 11 },
          data: [{ yAxis: 80 }],
        },
      },
    ],
  };
});

/* --------------------------------------------------------------- 图表 2 */
const heatmapData = computed(() => (heatmap.value?.data || []).filter((item) => Array.isArray(item)));
const heatmapOption = computed(() => {
  const xLabels = heatmap.value?.x_labels || [];
  const yLabels = heatmap.value?.y_labels || [];
  const values = heatmapData.value.map((item) => Number(item[2]) || 0);
  const maxValue = Number(heatmap.value?.max_value) || (values.length ? Math.max(...values) : 0);
  return {
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const x = xLabels[params?.value?.[0]] ?? '-';
        const y = yLabels[params?.value?.[1]] ?? '-';
        return `${y} ${x}:00<br/>叫车需求：${thousands(params?.value?.[2], 2)} 单/小时`;
      },
    },
    grid: { left: 10, right: 16, top: 12, bottom: 56, containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#4b5563' },
    },
    visualMap: {
      min: 0,
      max: maxValue || 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 110,
      textStyle: { color: '#6b7280', fontSize: 11 },
      inRange: { color: ['#eaf1fd', '#9dc0f6', '#2b6de5', '#1b3f8f'] },
    },
    series: [
      {
        name: '叫车需求',
        type: 'heatmap',
        data: heatmapData.value,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,0.35)' },
        },
      },
    ],
  };
});

/* --------------------------------------------------------------- 图表 3 */
const regionOption = computed(() => {
  const list = [...(regionRank.value || [])]
    .sort((a, b) => (b.demand || 0) - (a.demand || 0))
    .slice(0, 10)
    .reverse();
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const item = list[params?.[0]?.dataIndex] || {};
        return `${item.region_name || '-'}<br/>叫车需求：${thousands(item.demand)} 单<br/>实际完成：${thousands(
          item.order_count
        )} 单<br/>未满足：${thousands(item.unfulfilled)} 单<br/>未满足率：${percent(
          item.unfulfil_rate
        )}<br/>单均收入：${money(item.avg_amount)} 元`;
      },
    },
    legend: { data: ['叫车需求', '实际完成'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 44, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      name: '订单数',
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.region_name),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#4b5563', fontSize: 11 },
    },
    series: [
      {
        name: '叫车需求',
        type: 'bar',
        barMaxWidth: 10,
        data: list.map((item) => item.demand ?? 0),
        itemStyle: { color: '#2b6de5', borderRadius: [0, 4, 4, 0] },
      },
      {
        name: '实际完成',
        type: 'bar',
        barMaxWidth: 10,
        data: list.map((item) => item.order_count ?? 0),
        itemStyle: { color: 'rgba(6,182,212,0.85)', borderRadius: [0, 4, 4, 0] },
      },
    ],
  };
});

/* --------------------------------------------------------------- 图表 4 */
const matrixData = computed(() => {
  const rows = regionMatrix.value?.matrix || [];
  const output = [];
  rows.forEach((row, y) => {
    (row || []).forEach((value, x) => {
      output.push([x, y, Number(value) || 0]);
    });
  });
  return output;
});

const matrixHeight = computed(() => {
  const count = (regionMatrix.value?.matrix || []).length;
  return Math.min(560, Math.max(300, 100 + count * 26));
});

const matrixOption = computed(() => {
  const yLabels = regionMatrix.value?.y_labels || [];
  const xLabels = regionMatrix.value?.x_labels || [];
  const maxValue = matrixData.value.length
    ? matrixData.value.reduce((acc, item) => Math.max(acc, item[2]), 0)
    : 0;
  return {
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const x = xLabels[params?.value?.[0]] ?? '-';
        const y = yLabels[params?.value?.[1]] ?? '-';
        return `${y} ${x}:00<br/>日均需求：${thousands(params?.value?.[2], 2)} 单/小时`;
      },
    },
    grid: { left: 10, right: 16, top: 12, bottom: 58, containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#4b5563', fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: maxValue || 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 110,
      textStyle: { color: '#6b7280', fontSize: 11 },
      inRange: { color: ['#eaf1fd', '#9dc0f6', '#2b6de5', '#1b3f8f'] },
    },
    series: [
      {
        name: '日均需求',
        type: 'heatmap',
        data: matrixData.value,
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,0.35)' },
        },
      },
    ],
  };
});

/* --------------------------------------------------------------- 图表 5 */
const weekdayOption = computed(() => {
  const list = weekday.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['叫车需求', '实际完成'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 44, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.weekday_label),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value',
      name: '订单数',
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '叫车需求',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.demand ?? 0),
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
        name: '实际完成',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.supply ?? 0),
        itemStyle: { color: '#10b981' },
      },
    ],
  };
});

/* --------------------------------------------------------------- 图表 6 */
const weatherOption = computed(() => {
  const list = weather.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['叫车需求', '实际完成', '满足率'], right: 0, top: 0 },
    grid: { left: 10, right: 16, top: 44, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.weather || '未知'),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: [
      {
        type: 'value',
        name: '订单数',
        splitLine: { lineStyle: { color: '#f1f4f9' } },
        axisLabel: { color: '#6b7280' },
      },
      {
        type: 'value',
        name: '满足率(%)',
        max: 100,
        splitLine: { show: false },
        axisLabel: { color: '#6b7280' },
      },
    ],
    series: [
      {
        name: '叫车需求',
        type: 'bar',
        barMaxWidth: 22,
        data: list.map((item) => item.demand ?? 0),
        itemStyle: { color: 'rgba(43,109,229,0.78)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '实际完成',
        type: 'bar',
        barMaxWidth: 22,
        data: list.map((item) => item.supply ?? 0),
        itemStyle: { color: 'rgba(6,182,212,0.8)', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '满足率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 6,
        data: list.map((item) => item.fulfil_rate ?? 0),
        itemStyle: { color: '#f59e0b' },
      },
    ],
  };
});

/* --------------------------------------------------------------- 数据加载 */
async function loadRegions() {
  const list = await regionApi.all();
  regions.value = list || [];
}

async function loadAll() {
  loading.value = true;
  const params = rangeParams.value;
  const summaryParams = { ...params, region_id: regionId.value || undefined };
  try {
    const [summaryData, hourlyData, heatmapResult, ranking, matrix, weekdayData, weatherData] =
      await Promise.all([
        demandApi.summary(summaryParams).catch(() => ({})),
        analysisApi.hourlyProfile(params).catch(() => []),
        analysisApi.heatmap(params).catch(() => ({})),
        analysisApi.regionRanking(params).catch(() => []),
        demandApi.regionHourMatrix(params).catch(() => ({})),
        analysisApi.weekdayProfile(params).catch(() => []),
        analysisApi.weatherImpact(params).catch(() => []),
      ]);
    summary.value = summaryData || {};
    hourly.value = hourlyData || [];
    heatmap.value = heatmapResult || {};
    regionRank.value = ranking || [];
    regionMatrix.value = matrix || {};
    weekday.value = weekdayData || [];
    weather.value = weatherData || [];
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}

function reset() {
  dateRange.value = recentRange(14);
  regionId.value = null;
  loadAll();
}

onMounted(async () => {
  await loadRegions().catch(() => {});
  await loadAll();
});
</script>

<style scoped>
.filter-bar .el-form-item {
  margin-right: 12px;
}
:deep(.el-rate) {
  height: 18px;
  line-height: 18px;
}
:deep(.el-rate__icon) {
  font-size: 13px;
  margin-right: 1px;
}
</style>
