<template>
  <div v-loading="loading">
    <PageHeader
      title="运营数据分析"
      description="从收入结构、时空分布、驾驶员绩效、车辆效率到异常预警多维度量化运营质量，为运力投放与排班决策提供数据依据。"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 统一日期区间筛选 -->
    <div class="filter-bar">
      <span class="text-muted">统计区间</span>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :clearable="false"
        :unlink-panels="true"
        @change="handleRangeChange"
      />
      <el-radio-group v-model="quickDays" size="small" @change="handleQuickRange">
        <el-radio-button :value="7">近 7 天</el-radio-button>
        <el-radio-button :value="30">近 30 天</el-radio-button>
        <el-radio-button :value="90">近 90 天</el-radio-button>
      </el-radio-group>
      <span class="text-muted" style="font-size: 12px">
        共 {{ spanDays }} 天 · 环比对照上一个等长周期
      </span>
    </div>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- ============================================ 运营总览 -->
      <el-tab-pane label="运营总览" name="overview" lazy>
        <el-row :gutter="14">
          <el-col v-for="card in kpiCards" :key="card.label" :xs="12" :sm="12" :md="6" :lg="6">
            <StatCard v-bind="card" class="mb-16" />
          </el-col>
        </el-row>

        <el-row :gutter="14" class="mb-16">
          <el-col :xs="24" :md="16">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">收入与订单趋势</div>
                <el-radio-group v-model="trendGroupBy" size="small" @change="loadTrend">
                  <el-radio-button value="day">按日</el-radio-button>
                  <el-radio-button value="week">按周</el-radio-button>
                  <el-radio-button value="month">按月</el-radio-button>
                </el-radio-group>
              </div>
              <ChartBox
                :option="incomeOption"
                :height="300"
                :loading="loading"
                :empty="!trendList.length"
              />
              <p class="chart-card__desc">
                折线为收入（左轴），柱状为订单量（右轴）。收入增幅低于订单量增幅，说明单均收入在下滑。
              </p>
            </div>
          </el-col>
          <el-col :xs="24" :md="8">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">支付方式占比</div>
              </div>
              <ChartBox
                :option="payTypeOption"
                :height="300"
                :loading="loading"
                :empty="!payTypeList.length"
              />
              <p class="chart-card__desc">环形图按订单量统计占比，中心为区间内总订单数。</p>
            </div>
          </el-col>
        </el-row>

        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">里程利用率</div>
            <span class="text-muted" style="font-size: 12px">载客率 = 载客里程 / 总里程</span>
          </div>
          <el-row :gutter="10">
            <el-col :xs="24" :sm="10">
              <ChartBox
                :option="loadRateOption"
                :height="250"
                :loading="loading"
                :empty="!loadRateInfo.total_mileage"
              />
            </el-col>
            <el-col :xs="24" :sm="14">
              <el-descriptions :column="2" size="small" border class="mileage-desc">
                <el-descriptions-item label="载客里程">
                  {{ thousands(loadRateInfo.loaded_mileage, 1) }} km
                </el-descriptions-item>
                <el-descriptions-item label="空驶里程">
                  {{ thousands(loadRateInfo.empty_mileage, 1) }} km
                </el-descriptions-item>
                <el-descriptions-item label="总里程">
                  {{ thousands(loadRateInfo.total_mileage, 1) }} km
                </el-descriptions-item>
                <el-descriptions-item label="订单数">
                  {{ thousands(loadRateInfo.order_count) }} 单
                </el-descriptions-item>
                <el-descriptions-item label="载客率">
                  <span class="text-success">{{ percent(loadRateInfo.load_rate) }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="空驶率">
                  <span :class="loadRateInfo.empty_rate > 40 ? 'text-danger' : 'text-warning'">
                    {{ percent(loadRateInfo.empty_rate) }}
                  </span>
                </el-descriptions-item>
              </el-descriptions>
              <p class="chart-card__desc">
                空驶率长期高于 40% 说明运力投放与需求分布不匹配，应结合区域排行与时段分布优化巡游路线。
              </p>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- ============================================ 时段与区域 -->
      <el-tab-pane label="时段与区域" name="profile" lazy>
        <el-row :gutter="14" class="mb-16">
          <el-col :xs="24" :md="14">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">24 小时需求—供给分布</div>
                <span class="text-muted" style="font-size: 12px">橙色柱 = 高峰时段</span>
              </div>
              <ChartBox
                :option="hourlyOption"
                :height="310"
                :loading="loading"
                :empty="!hourlyList.length"
              />
              <p class="chart-card__desc">
                柱=叫车需求，折线=实际完成与未满足量；未满足量抬升的时段即为运力缺口时段。
              </p>
            </div>
          </el-col>
          <el-col :xs="24" :md="10">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">星期分布</div>
                <span class="text-muted" style="font-size: 12px">紫色柱 = 周末</span>
              </div>
              <ChartBox
                :option="weekdayOption"
                :height="310"
                :loading="loading"
                :empty="!weekdayList.length"
              />
              <p class="chart-card__desc">对比工作日与周末的需求差异，用于差异化排班。</p>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="14" class="mb-16">
          <el-col :xs="24" :md="15">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">星期 × 小时需求热力图</div>
                <span class="text-muted" style="font-size: 12px">颜色越深需求越高</span>
              </div>
              <ChartBox
                :option="heatmapOption"
                :height="350"
                :loading="loading"
                :empty="!heatmapPoints.length"
              />
            </div>
          </el-col>
          <el-col :xs="24" :md="9">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">区域对比雷达</div>
                <el-select
                  v-model="compareRegions"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :multiple-limit="6"
                  size="small"
                  placeholder="选择区域（最多 6 个）"
                  class="region-picker"
                  @change="loadRegionCompare"
                >
                  <el-option
                    v-for="item in regionList"
                    :key="item.region_id"
                    :label="item.region_name"
                    :value="item.region_id"
                  />
                </el-select>
              </div>
              <ChartBox
                :option="radarOption"
                :height="350"
                :loading="loading"
                :empty="!compareReady"
              />
              <p class="chart-card__desc">
                各指标以所选区域中的最大值归一化到 0-100，悬停可查看原始值。
              </p>
            </div>
          </el-col>
        </el-row>

        <div class="table-card">
          <div class="table-toolbar">
            <div class="chart-card__title">区域排行</div>
            <span class="text-muted" style="font-size: 12px">
              未满足率 &gt; 15% 标红，空驶率 &gt; 40% 标橙，点击表头可排序
            </span>
          </div>
          <el-table :data="regionList" size="small" stripe height="380" border>
            <el-table-column type="index" label="#" width="48" align="center" />
            <el-table-column prop="region_name" label="区域" min-width="120" sortable show-overflow-tooltip />
            <el-table-column prop="region_type" label="功能区" width="110" sortable show-overflow-tooltip />
            <el-table-column prop="demand" label="需求" width="88" align="right" sortable />
            <el-table-column prop="order_count" label="订单量" width="92" align="right" sortable />
            <el-table-column prop="income" label="收入(元)" width="118" align="right" sortable>
              <template #default="{ row }">{{ money(row.income) }}</template>
            </el-table-column>
            <el-table-column prop="unfulfil_rate" label="未满足率" width="110" align="right" sortable>
              <template #default="{ row }">
                <el-tag v-if="row.unfulfil_rate > 15" type="danger" size="small" effect="light">
                  {{ percent(row.unfulfil_rate) }}
                </el-tag>
                <span v-else>{{ percent(row.unfulfil_rate) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="empty_rate" label="空驶率" width="104" align="right" sortable>
              <template #default="{ row }">
                <el-tag v-if="row.empty_rate > 40" type="warning" size="small" effect="light">
                  {{ percent(row.empty_rate) }}
                </el-tag>
                <span v-else>{{ percent(row.empty_rate) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="avg_amount" label="单均收入" width="106" align="right" sortable>
              <template #default="{ row }">{{ money(row.avg_amount) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- ============================================ 驾驶员绩效 -->
      <el-tab-pane label="驾驶员绩效" name="driver" lazy>
        <div class="filter-bar">
          <span class="text-muted">排行范围</span>
          <el-radio-group v-model="driverTopN" size="small" @change="loadDriverTab">
            <el-radio-button :value="10">TOP 10</el-radio-button>
            <el-radio-button :value="20">TOP 20</el-radio-button>
            <el-radio-button :value="50">TOP 50</el-radio-button>
          </el-radio-group>
          <span class="text-muted">排序字段</span>
          <el-select v-model="driverSortBy" size="small" style="width: 140px" @change="loadDriverTab">
            <el-option label="综合得分" value="score" />
            <el-option label="收入" value="income" />
            <el-option label="订单量" value="order_count" />
            <el-option label="评分" value="rating" />
          </el-select>
          <span class="text-muted" style="font-size: 12px">
            综合得分 = 收入 60% + 订单量 25% + 评分 15%（归一化加权）
          </span>
        </div>

        <div class="table-card mb-16">
          <el-table :data="driverList" size="small" stripe height="440" border>
            <el-table-column type="index" label="排名" width="66" align="center" />
            <el-table-column prop="name" label="姓名" width="100" show-overflow-tooltip />
            <el-table-column label="评分" width="180">
              <template #default="{ row }">
                <el-rate
                  :model-value="Number(row.rating) || 0"
                  disabled
                  show-score
                  score-template="{value}"
                  :max="5"
                />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="84" align="center">
              <template #default="{ row }">
                <el-tag :type="driverStatus(row.status).type" size="small">
                  {{ driverStatus(row.status).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="order_count" label="订单量" width="92" align="right" sortable />
            <el-table-column prop="income" label="总收入(元)" width="120" align="right" sortable>
              <template #default="{ row }">{{ money(row.income) }}</template>
            </el-table-column>
            <el-table-column prop="loaded_mileage" label="载客里程" width="112" align="right" sortable>
              <template #default="{ row }">{{ thousands(row.loaded_mileage, 1) }}</template>
            </el-table-column>
            <el-table-column prop="empty_rate" label="空驶率" width="98" align="right" sortable>
              <template #default="{ row }">{{ percent(row.empty_rate) }}</template>
            </el-table-column>
            <el-table-column prop="avg_amount" label="单均收入" width="104" align="right" sortable>
              <template #default="{ row }">{{ money(row.avg_amount) }}</template>
            </el-table-column>
            <el-table-column prop="score" label="综合得分" min-width="160">
              <template #default="{ row }">
                <el-progress
                  :percentage="scoreOf(row.score)"
                  :stroke-width="10"
                  :color="scoreColor"
                  :format="scoreFormat"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">TOP10 驾驶员收入</div>
            <span class="text-muted" style="font-size: 12px">基于当前排行范围的前 10 名</span>
          </div>
          <ChartBox
            :option="driverBarOption"
            :height="330"
            :loading="loading"
            :empty="!driverList.length"
          />
          <p class="chart-card__desc">
            收入差距明显时，可结合空驶率与单均收入判断是接单量不足还是路线效率问题。
          </p>
        </div>
      </el-tab-pane>

      <!-- ============================================ 车辆效率 -->
      <el-tab-pane label="车辆效率" name="vehicle" lazy>
        <div class="filter-bar">
          <span class="text-muted">排行范围</span>
          <el-radio-group v-model="vehicleTopN" size="small" @change="loadVehicleTab">
            <el-radio-button :value="10">TOP 10</el-radio-button>
            <el-radio-button :value="20">TOP 20</el-radio-button>
            <el-radio-button :value="50">TOP 50</el-radio-button>
          </el-radio-group>
          <span class="text-muted">收入排序</span>
          <el-radio-group v-model="vehicleOrder" size="small" @change="loadVehicleTab">
            <el-radio-button value="desc">从高到低</el-radio-button>
            <el-radio-button value="asc">从低到高</el-radio-button>
          </el-radio-group>
          <span class="text-muted" style="font-size: 12px">每公里收入 = 总收入 / 总里程</span>
        </div>

        <div class="table-card mb-16">
          <el-table :data="vehicleList" size="small" stripe height="400" border>
            <el-table-column type="index" label="#" width="48" align="center" />
            <el-table-column prop="plate_number" label="车牌号" width="126" />
            <el-table-column prop="brand_model" label="品牌型号" min-width="150" show-overflow-tooltip />
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">
                <el-tag :type="vehicleStatus(row.status).type" size="small">
                  {{ row.status_text || vehicleStatus(row.status).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="order_count" label="订单量" width="92" align="right" sortable />
            <el-table-column prop="income" label="总收入(元)" width="122" align="right" sortable>
              <template #default="{ row }">{{ money(row.income) }}</template>
            </el-table-column>
            <el-table-column prop="total_mileage" label="总里程(km)" width="122" align="right" sortable>
              <template #default="{ row }">{{ thousands(row.total_mileage, 1) }}</template>
            </el-table-column>
            <el-table-column prop="empty_rate" label="空驶率" width="100" align="right" sortable>
              <template #default="{ row }">{{ percent(row.empty_rate) }}</template>
            </el-table-column>
            <el-table-column prop="income_per_km" label="每公里收入" width="118" align="right" sortable>
              <template #default="{ row }">{{ money(row.income_per_km) }}</template>
            </el-table-column>
          </el-table>
        </div>

        <el-row :gutter="14">
          <el-col :xs="24" :md="15">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">里程—收入分布</div>
                <span class="text-muted" style="font-size: 12px">点大小 = 订单量</span>
              </div>
              <ChartBox
                :option="scatterOption"
                :height="320"
                :loading="loading"
                :empty="!vehicleList.length"
              />
              <p class="chart-card__desc">
                位于右下方（里程高、收入低）的车辆效率偏低，建议核查巡游路线或调整排班。
              </p>
            </div>
          </el-col>
          <el-col :xs="24" :md="9">
            <div class="chart-card">
              <div class="chart-card__head">
                <div class="chart-card__title">车辆状态构成</div>
              </div>
              <ChartBox
                :option="vehicleStatusOption"
                :height="320"
                :loading="loading"
                :empty="!vehicleList.length"
              />
              <p class="chart-card__desc">按当前排行结果中的车辆统计状态分布。</p>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ============================================ 异常预警 -->
      <el-tab-pane label="异常预警" name="alert" lazy>
        <div class="filter-bar">
          <span class="text-muted">统计天数</span>
          <el-radio-group v-model="alertDays" size="small" @change="loadAlertTab">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="14">近 14 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
          </el-radio-group>
          <span class="text-muted" style="font-size: 12px">
            预警不依赖上方日期区间，按所选天数滚动计算
          </span>
        </div>

        <el-row :gutter="14">
          <el-col v-for="card in alertCards" :key="card.label" :xs="12" :sm="12" :md="6">
            <StatCard v-bind="card" class="mb-16" />
          </el-col>
        </el-row>

        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">
              预警明细
              <el-tag v-if="filteredAlerts.length" type="danger" size="small" effect="dark">
                {{ filteredAlerts.length }}
              </el-tag>
            </div>
            <div class="alert-toolbar">
              <el-radio-group v-model="alertLevel" size="small">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="high">高</el-radio-button>
                <el-radio-button value="medium">中</el-radio-button>
                <el-radio-button value="low">低</el-radio-button>
              </el-radio-group>
              <el-input
                v-model="alertKeyword"
                placeholder="搜索标题 / 内容 / 目标"
                clearable
                size="small"
                style="width: 220px"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
          </div>

          <el-scrollbar max-height="560px">
            <el-empty
              v-if="!filteredAlerts.length"
              description="暂无符合条件的预警，运营状况良好"
              :image-size="80"
            />
            <div
              v-for="(item, index) in filteredAlerts"
              :key="`${item.type}-${item.target}-${index}`"
              class="alert-item"
              :class="`alert-item--${item.level}`"
            >
              <el-tag :type="levelTag(item.level)" size="small" effect="dark">
                {{ levelText(item.level) }}
              </el-tag>
              <div class="alert-item__body">
                <div class="alert-item__title">
                  {{ item.title }}
                  <el-tag size="small" type="info" effect="plain">{{ item.type }}</el-tag>
                </div>
                <div class="alert-item__content">{{ item.content }}</div>
                <div v-if="item.suggestion" class="alert-item__suggestion">
                  <el-icon><InfoFilled /></el-icon>{{ item.suggestion }}
                </div>
              </div>
              <div class="alert-item__target">
                <div class="alert-item__target-label">预警目标</div>
                <div class="alert-item__target-value">{{ item.target || '-' }}</div>
                <div v-if="item.value !== null && item.value !== undefined" class="mono text-muted">
                  {{ item.value }}{{ item.unit || '' }}
                </div>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import ChartBox from '../components/ChartBox.vue';
import { analysisApi } from '../api';
import {
  DRIVER_STATUS,
  VEHICLE_STATUS,
  money,
  percent,
  recentRange,
  thousands,
} from '../utils/format';

/* ------------------------------------------------------------------ 状态 */
const activeTab = ref('overview');
const dateRange = ref(recentRange(30));
const quickDays = ref(30);
const pending = ref(0);
const loading = computed(() => pending.value > 0);
const tabLoaded = reactive({
  overview: false,
  profile: false,
  driver: false,
  vehicle: false,
  alert: false,
});

/* 运营总览 */
const kpi = ref({});
const trendList = ref([]);
const trendGroupBy = ref('day');
const payTypeList = ref([]);
const loadRateInfo = ref({});

/* 时段与区域 */
const hourlyList = ref([]);
const weekdayList = ref([]);
const heatmapData = ref({});
const regionList = ref([]);
const compareRegions = ref([]);
const compareData = ref({ indicators: [], series: [] });

/* 驾驶员绩效 */
const driverTopN = ref(10);
const driverSortBy = ref('score');
const driverList = ref([]);

/* 车辆效率 */
const vehicleTopN = ref(10);
const vehicleOrder = ref('desc');
const vehicleList = ref([]);

/* 异常预警 */
const alertDays = ref(7);
const alertList = ref([]);
const alertLevel = ref('all');
const alertKeyword = ref('');

const PALETTE = ['#2b6de5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
const RAW_LABELS = {
  income: '总收入(元)',
  order_count: '订单量',
  demand: '需求量',
  avg_amount: '单均收入(元)',
};

/* ------------------------------------------------------------------ 区间工具 */
function resolvedRange() {
  const value = dateRange.value;
  if (Array.isArray(value) && value.length === 2 && value[0] && value[1]) return value;
  return recentRange(30);
}

function rangeParams() {
  const [start, end] = resolvedRange();
  return { start_date: start, end_date: end };
}

const spanDays = computed(() => {
  const [start, end] = resolvedRange();
  const first = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  if (Number.isNaN(first.getTime()) || Number.isNaN(last.getTime())) return 0;
  return Math.max(0, Math.round((last - first) / 86400000) + 1);
});

/** 统一 loading 计数 + 错误兜底（错误提示由拦截器负责） */
function withLoading(task) {
  pending.value += 1;
  return Promise.resolve()
    .then(task)
    .catch(() => {
      /* 拦截器已统一提示 */
    })
    .finally(() => {
      pending.value -= 1;
    });
}

/* ------------------------------------------------------------------ Tab 懒加载 */
async function loadOverviewTab() {
  await Promise.all([
    analysisApi.overview(rangeParams()).then((data) => {
      kpi.value = data || {};
    }),
    analysisApi
      .incomeTrend({ ...rangeParams(), group_by: trendGroupBy.value })
      .then((data) => {
        trendList.value = Array.isArray(data) ? data : [];
      }),
    analysisApi.payType(rangeParams()).then((data) => {
      payTypeList.value = Array.isArray(data) ? data : [];
    }),
    analysisApi.loadRate(rangeParams()).then((data) => {
      loadRateInfo.value = data || {};
    }),
  ]);
}

async function loadProfileTab() {
  await Promise.all([
    analysisApi.hourlyProfile(rangeParams()).then((data) => {
      hourlyList.value = Array.isArray(data) ? data : [];
    }),
    analysisApi.weekdayProfile(rangeParams()).then((data) => {
      weekdayList.value = Array.isArray(data) ? data : [];
    }),
    analysisApi.heatmap(rangeParams()).then((data) => {
      heatmapData.value = data || {};
    }),
    analysisApi.regionRanking(rangeParams()).then((data) => {
      regionList.value = Array.isArray(data) ? data : [];
      if (!compareRegions.value.length) {
        compareRegions.value = regionList.value
          .slice(0, 4)
          .map((item) => item.region_id)
          .filter((id) => id !== null && id !== undefined);
      }
    }),
  ]);
  await loadRegionCompare();
}

async function loadDriverTab() {
  await withLoading(async () => {
    const data = await analysisApi.driverRanking({
      ...rangeParams(),
      top_n: driverTopN.value,
      sort_by: driverSortBy.value,
    });
    driverList.value = Array.isArray(data) ? data : [];
  });
}

async function loadVehicleTab() {
  await withLoading(async () => {
    const data = await analysisApi.vehicleEfficiency({
      ...rangeParams(),
      top_n: vehicleTopN.value,
      order: vehicleOrder.value,
    });
    vehicleList.value = Array.isArray(data) ? data : [];
  });
}

async function loadAlertTab() {
  await withLoading(async () => {
    const data = await analysisApi.abnormalAlert({ days: alertDays.value });
    alertList.value = Array.isArray(data) ? data : [];
  });
}

const tabLoaders = {
  overview: () => withLoading(loadOverviewTab),
  profile: () => withLoading(loadProfileTab),
  driver: loadDriverTab,
  vehicle: loadVehicleTab,
  alert: loadAlertTab,
};

function ensureTab(tab, force = false) {
  const loader = tabLoaders[tab];
  if (!loader) return;
  if (tabLoaded[tab] && !force) return;
  tabLoaded[tab] = true;
  loader();
}

function handleTabChange(name) {
  ensureTab(name);
}

function refreshCurrent() {
  ensureTab(activeTab.value, true);
}

function resetTabs() {
  Object.keys(tabLoaded).forEach((key) => {
    tabLoaded[key] = false;
  });
}

function handleRangeChange() {
  quickDays.value = null;
  resetTabs();
  ensureTab(activeTab.value, true);
}

function handleQuickRange(days) {
  dateRange.value = recentRange(days);
  resetTabs();
  ensureTab(activeTab.value, true);
}

/* 收入趋势（分组切换） */
function loadTrend() {
  return withLoading(async () => {
    const data = await analysisApi.incomeTrend({
      ...rangeParams(),
      group_by: trendGroupBy.value,
    });
    trendList.value = Array.isArray(data) ? data : [];
  });
}

/* 区域雷达（选择变化） */
function loadRegionCompare() {
  return withLoading(async () => {
    const ids = (compareRegions.value || []).filter((id) => id !== null && id !== undefined);
    if (!ids.length) {
      compareData.value = { indicators: [], series: [] };
      return;
    }
    const data = await analysisApi.regionCompare({
      ...rangeParams(),
      region_ids: ids.join(','),
    });
    compareData.value = data && typeof data === 'object' ? data : { indicators: [], series: [] };
  });
}

/* ------------------------------------------------------------------ 运营总览 */
const kpiCards = computed(() => {
  const data = kpi.value || {};
  const vs = data.vs_prev || {};
  return [
    {
      label: '订单总量',
      value: data.order_count ?? 0,
      unit: '单',
      icon: 'Tickets',
      tone: 'blue',
      change: vs.order_count ?? null,
      changeLabel: '环比',
      sub: `日均 ${thousands((data.order_count ?? 0) / Math.max(1, data.span_days ?? spanDays.value), 0)} 单`,
    },
    {
      label: '总收入',
      value: data.income ?? 0,
      unit: '元',
      icon: 'Money',
      tone: 'green',
      digits: 2,
      change: vs.income ?? null,
      changeLabel: '环比',
      sub: `日均 ${money((data.income ?? 0) / Math.max(1, data.span_days ?? spanDays.value))} 元`,
    },
    {
      label: '单均收入',
      value: data.avg_amount ?? 0,
      unit: '元',
      icon: 'Coin',
      tone: 'cyan',
      digits: 2,
      change: vs.avg_amount ?? null,
      changeLabel: '环比',
      sub: `车均收入 ${money(data.income_per_vehicle)} 元`,
    },
    {
      label: '空驶率',
      value: data.empty_rate ?? 0,
      unit: '%',
      icon: 'Odometer',
      tone: 'orange',
      digits: 2,
      change: vs.empty_rate ?? null,
      changeLabel: '环比',
      inverse: true,
      sub: `空驶里程 ${thousands(data.empty_mileage, 1)} km`,
    },
    {
      label: '需求满足率',
      value: data.fulfil_rate ?? 0,
      unit: '%',
      icon: 'CircleCheck',
      tone: 'purple',
      digits: 2,
      change: vs.fulfil_rate ?? null,
      changeLabel: '环比',
      sub: `叫车 ${thousands(data.request_count)} 单 / 完成 ${thousands(data.fulfilled_count)} 单`,
    },
    {
      label: '活跃车辆',
      value: data.active_vehicles ?? 0,
      unit: '台',
      icon: 'Van',
      tone: 'blue',
      sub: `车均订单 ${thousands(data.orders_per_vehicle, 1)} 单`,
    },
    {
      label: '活跃驾驶员',
      value: data.active_drivers ?? 0,
      unit: '人',
      icon: 'UserFilled',
      tone: 'green',
      sub: `高峰收入占比 ${percent(data.peak_income_ratio)}`,
    },
    {
      label: '平均运距',
      value: data.avg_distance ?? 0,
      unit: 'km',
      icon: 'Guide',
      tone: 'cyan',
      digits: 2,
      sub: `平均时长 ${thousands(data.avg_duration, 1)} 分钟`,
    },
  ];
});

const incomeOption = computed(() => {
  const list = trendList.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['收入(元)', '订单量'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: true,
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
        name: '订单量',
        type: 'bar',
        yAxisIndex: 1,
        barWidth: '46%',
        data: list.map((item) => item.order_count),
        itemStyle: { color: 'rgba(6,182,212,0.45)', borderRadius: [4, 4, 0, 0] },
      },
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
    ],
  };
});

const payTypeOption = computed(() => {
  const list = payTypeList.value || [];
  const total = list.reduce((sum, item) => sum + (Number(item.order_count) || 0), 0);
  return {
    color: PALETTE,
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const extra = params.data || {};
        return `${params.name}<br/>订单 ${thousands(params.value)} 单（${params.percent}%）<br/>收入 ${money(extra.income)} 元`;
      },
    },
    legend: {
      orient: 'vertical',
      right: 0,
      top: 'middle',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#6b7280', fontSize: 12 },
      formatter: (name) => {
        const item = list.find((row) => row.pay_type === name);
        return item ? `${name} ${percent(item.ratio)}` : name;
      },
    },
    title: {
      text: thousands(total),
      subtext: '总订单数',
      left: '35%',
      top: '42%',
      textAlign: 'center',
      textStyle: { fontSize: 20, fontWeight: 600, color: '#1f2937' },
      subtextStyle: { fontSize: 12, color: '#6b7280' },
    },
    series: [
      {
        name: '支付方式',
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['35%', '52%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        labelLine: { show: false },
        data: list.map((item) => ({
          name: item.pay_type,
          value: Number(item.order_count) || 0,
          income: item.income,
        })),
      },
    ],
  };
});

const loadRateOption = computed(() => {
  const data = loadRateInfo.value || {};
  const rate = Number(data.load_rate) || 0;
  return {
    tooltip: { formatter: (params) => `${params.name}：${params.value}%` },
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: '92%',
        center: ['50%', '56%'],
        progress: {
          show: true,
          width: 14,
          itemStyle: { color: rate >= 60 ? '#10b981' : rate >= 45 ? '#2b6de5' : '#f59e0b' },
        },
        axisLine: { lineStyle: { width: 14, color: [[1, '#eef2f8']] } },
        axisTick: { show: false },
        splitLine: { length: 9, lineStyle: { color: '#dbe3ee', width: 1 } },
        axisLabel: { color: '#9aa4b2', fontSize: 10, distance: 14 },
        pointer: { width: 5, itemStyle: { color: '#2b6de5' } },
        anchor: { show: true, size: 12, itemStyle: { color: '#2b6de5' } },
        title: { offsetCenter: [0, '82%'], color: '#6b7280', fontSize: 12 },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '46%'],
          color: '#1f2937',
          fontSize: 24,
          fontWeight: 600,
          formatter: (value) => `${Number(value).toFixed(1)}%`,
        },
        data: [{ value: Number(rate.toFixed(2)), name: '载客率' }],
      },
    ],
  };
});

/* ------------------------------------------------------------------ 时段与区域 */
const hourlyOption = computed(() => {
  const list = hourlyList.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['叫车需求', '实际完成', '未满足'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 42, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.hour_label),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280', fontSize: 10, interval: 0 },
    },
    yAxis: [
      {
        type: 'value',
        name: '订单数',
        splitLine: { lineStyle: { color: '#f1f4f9' } },
        axisLabel: { color: '#6b7280' },
      },
    ],
    series: [
      {
        name: '叫车需求',
        type: 'bar',
        barWidth: '56%',
        data: list.map((item) => ({
          value: item.demand,
          itemStyle: {
            color: item.is_peak ? '#f59e0b' : 'rgba(43,109,229,0.78)',
            borderRadius: [4, 4, 0, 0],
          },
        })),
      },
      {
        name: '实际完成',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: list.map((item) => item.supply),
        itemStyle: { color: '#10b981' },
      },
      {
        name: '未满足',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: list.map((item) => item.unfulfilled),
        itemStyle: { color: '#ef4444' },
        lineStyle: { type: 'dashed' },
      },
    ],
  };
});

const weekdayOption = computed(() => {
  const list = weekdayList.value || [];
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['叫车需求', '实际完成'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 42, bottom: 6, containLabel: true },
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
        type: 'bar',
        barWidth: '48%',
        data: list.map((item) => ({
          value: item.demand,
          itemStyle: {
            color: item.is_weekend ? '#8b5cf6' : 'rgba(43,109,229,0.78)',
            borderRadius: [4, 4, 0, 0],
          },
        })),
      },
      {
        name: '实际完成',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: list.map((item) => item.supply),
        itemStyle: { color: '#10b981' },
      },
    ],
  };
});

const heatmapPoints = computed(() => {
  const data = heatmapData.value || {};
  return Array.isArray(data.data) ? data.data : [];
});

const heatmapOption = computed(() => {
  const data = heatmapData.value || {};
  const xLabels = Array.isArray(data.x_labels) ? data.x_labels : [];
  const yLabels = Array.isArray(data.y_labels) ? data.y_labels : [];
  const maxValue = Number(data.max_value) > 0 ? Number(data.max_value) : 1;
  return {
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const point = params.value || [];
        const hour = xLabels[point[0]] ?? point[0];
        const day = yLabels[point[1]] ?? point[1];
        return `${day} ${hour}:00<br/>平均需求 ${thousands(point[2], 1)} 单/小时`;
      },
    },
    grid: { left: 10, right: 16, top: 10, bottom: 58, containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280', fontSize: 10, interval: 0 },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280' },
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      itemWidth: 12,
      itemHeight: 110,
      textStyle: { color: '#6b7280', fontSize: 11 },
      inRange: { color: ['#eaf0fd', '#9dc0f5', '#2b6de5', '#1b2a41'] },
    },
    series: [
      {
        name: '平均需求',
        type: 'heatmap',
        data: heatmapPoints.value,
        label: { show: false },
        itemStyle: { borderColor: '#fff', borderWidth: 1 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,0.35)' } },
      },
    ],
  };
});

const compareReady = computed(() => {
  const data = compareData.value || {};
  return (data.indicators || []).length > 0 && (data.series || []).length > 0;
});

const radarOption = computed(() => {
  const data = compareData.value || {};
  const indicators = Array.isArray(data.indicators) ? data.indicators : [];
  const series = Array.isArray(data.series) ? data.series : [];
  const ready = indicators.length > 0 && series.length > 0;
  return {
    color: PALETTE,
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const raw = (params.data || {}).raw || {};
        const keys = Object.keys(raw);
        const rows = keys.length
          ? keys.map((key) => `${RAW_LABELS[key] || key}：${thousands(raw[key], 2)}`)
          : (params.value || []).map(
              (value, index) => `${indicators[index] ? indicators[index].name : index}：${value}`
            );
        return `${params.name}<br/>${rows.join('<br/>')}`;
      },
    },
    legend: {
      bottom: 0,
      data: series.map((item) => item.name),
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#6b7280', fontSize: 12 },
    },
    radar: {
      indicator: ready
        ? indicators.map((item) => ({ name: item.name, max: Number(item.max) || 100 }))
        : [{ name: '暂无数据', max: 100 }],
      radius: '62%',
      center: ['50%', '46%'],
      splitLine: { lineStyle: { color: '#e6eaf0' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f9fbfe'] } },
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisName: { color: '#6b7280', fontSize: 12 },
    },
    series: ready
      ? [
          {
            type: 'radar',
            symbolSize: 4,
            areaStyle: { opacity: 0.12 },
            data: series.map((item, index) => ({
              name: item.name,
              value: Array.isArray(item.value) ? item.value : [],
              raw: item.raw || {},
              itemStyle: { color: PALETTE[index % PALETTE.length] },
              lineStyle: { color: PALETTE[index % PALETTE.length] },
            })),
          },
        ]
      : [],
  };
});

/* ------------------------------------------------------------------ 驾驶员绩效 */
function driverStatus(status) {
  return DRIVER_STATUS[status] || { text: '未知', type: 'info' };
}

function scoreOf(score) {
  const value = Number(score) || 0;
  return Math.min(100, Math.max(0, Math.round(value * 10) / 10));
}

function scoreColor(value) {
  if (value >= 80) return '#10b981';
  if (value >= 60) return '#2b6de5';
  if (value >= 40) return '#f59e0b';
  return '#ef4444';
}

function scoreFormat(value) {
  return `${Number(value).toFixed(1)} 分`;
}

const driverBarOption = computed(() => {
  const list = (driverList.value || []).slice(0, 10).reverse();
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const item = list[params[0].dataIndex] || {};
        return `${item.name || '-'}<br/>收入 ${money(item.income)} 元<br/>订单 ${thousands(
          item.order_count
        )} 单<br/>综合得分 ${scoreOf(item.score).toFixed(1)} 分`;
      },
    },
    grid: { left: 10, right: 70, top: 14, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      name: '收入(元)',
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.name),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#4b5563' },
    },
    series: [
      {
        name: '收入',
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
              { offset: 0, color: '#95b6f3' },
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

/* ------------------------------------------------------------------ 车辆效率 */
function vehicleStatus(status) {
  return VEHICLE_STATUS[status] || { text: '未知', type: 'info' };
}

const scatterOption = computed(() => {
  const list = vehicleList.value || [];
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const point = params.data || [];
        return `${point[3] || '-'}<br/>总里程 ${thousands(point[0], 1)} km<br/>收入 ${money(
          point[1]
        )} 元<br/>订单 ${thousands(point[2])} 单`;
      },
    },
    grid: { left: 10, right: 26, top: 34, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      name: '总里程(km)',
      nameTextStyle: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value',
      name: '收入(元)',
      nameTextStyle: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '车辆',
        type: 'scatter',
        symbolSize: (value) => {
          const orders = Number((value || [])[2]) || 0;
          return Math.max(9, Math.min(40, 9 + Math.sqrt(orders)));
        },
        itemStyle: {
          color: 'rgba(43,109,229,0.55)',
          borderColor: '#2b6de5',
          borderWidth: 1,
        },
        data: list.map((item) => [
          item.total_mileage,
          item.income,
          item.order_count,
          item.plate_number,
        ]),
      },
    ],
  };
});

const vehicleStatusOption = computed(() => {
  const list = vehicleList.value || [];
  const counter = {};
  list.forEach((item) => {
    const name = item.status_text || vehicleStatus(item.status).text;
    counter[name] = (counter[name] || 0) + 1;
  });
  const colors = { 在营: '#10b981', 停运: '#94a3b8', 维修: '#f59e0b' };
  const data = Object.keys(counter).map((name) => ({
    name,
    value: counter[name],
    itemStyle: { color: colors[name] || '#2b6de5' },
  }));
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 台（{d}%）' },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#6b7280', fontSize: 12 },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '68%'],
        center: ['50%', '46%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { color: '#4b5563', fontSize: 12, formatter: '{b} {c}' },
        data,
      },
    ],
  };
});

/* ------------------------------------------------------------------ 异常预警 */
const alertCards = computed(() => {
  const list = alertList.value || [];
  const countOf = (level) => list.filter((item) => item.level === level).length;
  return [
    {
      label: '预警总数',
      value: list.length,
      unit: '条',
      icon: 'Bell',
      tone: 'blue',
      sub: `近 ${alertDays.value} 天运营扫描结果`,
    },
    {
      label: '高优先级',
      value: countOf('high'),
      unit: '条',
      icon: 'WarningFilled',
      tone: 'red',
      sub: '需立即处置',
    },
    {
      label: '中优先级',
      value: countOf('medium'),
      unit: '条',
      icon: 'Warning',
      tone: 'orange',
      sub: '建议尽快跟进',
    },
    {
      label: '低优先级',
      value: countOf('low'),
      unit: '条',
      icon: 'InfoFilled',
      tone: 'cyan',
      sub: '持续观察即可',
    },
  ];
});

const filteredAlerts = computed(() => {
  const keyword = (alertKeyword.value || '').trim().toLowerCase();
  return (alertList.value || []).filter((item) => {
    if (alertLevel.value !== 'all' && item.level !== alertLevel.value) return false;
    if (!keyword) return true;
    return [item.title, item.content, item.suggestion, item.target, item.type]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(keyword);
  });
});

function levelTag(level) {
  return { high: 'danger', medium: 'warning', low: 'info' }[level] || 'info';
}

function levelText(level) {
  return { high: '高', medium: '中', low: '低' }[level] || '低';
}

/* ------------------------------------------------------------------ 初始化 */
onMounted(() => {
  ensureTab(activeTab.value, true);
});
</script>

<style scoped>
.mileage-desc {
  margin-top: 8px;
}
.region-picker {
  width: 190px;
}
.alert-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
.alert-item__target {
  flex-shrink: 0;
  width: 120px;
  text-align: right;
}
.alert-item__target-label {
  font-size: 11px;
  color: #9aa4b2;
}
.alert-item__target-value {
  font-size: 12.5px;
  color: var(--app-text);
  font-weight: 600;
  margin-top: 2px;
  word-break: break-all;
}
@media (max-width: 768px) {
  .alert-item__target {
    display: none;
  }
}
</style>
