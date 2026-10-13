<template>
  <div v-loading="booting">
    <PageHeader
      title="需求预测中心"
      description="基于历史叫车需求，采用季节朴素法、季节移动平均、Holt-Winters 三次指数平滑、多元线性回归与组合模型进行滚动回测，自动选择最优模型并预测未来逐时需求。"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="metaLoading" @click="reloadMeta">刷新评估数据</el-button>
      </template>
    </PageHeader>

    <!-- ------------------------------------------------------------ 控制区 -->
    <div class="filter-bar">
      <span class="filter-label">预测区域</span>
      <el-select v-model="form.regionKey" style="width: 240px" placeholder="请选择预测区域">
        <el-option
          v-for="item in regions"
          :key="String(item.region_id)"
          :label="item.region_name"
          :value="item.region_id === null ? 'all' : item.region_id"
        >
          <span>{{ item.region_name }}</span>
          <span class="text-muted option-extra">{{ thousands(item.request_count) }} 条需求</span>
        </el-option>
      </el-select>

      <span class="filter-label">预测时长</span>
      <el-select v-model="form.horizon" style="width: 150px">
        <el-option v-for="item in HORIZONS" :key="item" :value="item" :label="`未来 ${item} 小时`" />
      </el-select>

      <span class="filter-label">
        自动选优
        <el-tooltip
          placement="top"
          content="开启后按主指标自动选择回测表现最好的模型（组合模型也参与竞争）；关闭则使用默认模型列表中的第一个可用模型"
        >
          <el-icon class="tip-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </span>
      <el-switch v-model="form.autoSelect" />

      <el-button type="primary" :icon="MagicStick" :loading="running" @click="runForecast">
        开始预测
      </el-button>
      <span class="text-muted hint">
        <el-icon><InfoFilled /></el-icon>
        含 3 折滚动回测，约需数秒到数十秒，执行期间请勿关闭页面
      </span>
    </div>

    <el-empty
      v-if="!result && !running"
      description="尚未获得预测结果：请选择区域与预测时长后点击「开始预测」"
    />

    <template v-if="result">
      <!-- -------------------------------------------------------- 结果概要 -->
      <div class="chart-card mb-16">
        <div class="chart-card__head">
          <div class="chart-card__title">预测结果概要</div>
          <span class="text-muted" style="font-size: 12px">
            滚动回测 → 自动选优 → 全量重训 → 未来 {{ result.horizon }} 小时逐时预测
          </span>
        </div>
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="预测区域">{{ result.region_name }}</el-descriptions-item>
          <el-descriptions-item label="最优模型">
            <el-tag type="success" effect="dark">{{ result.model_label }}</el-tag>
            <el-tag v-if="!runFlags.autoSelect" type="info" size="small" effect="plain" class="ml-4">
              人工指定
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="历史天数">{{ result.history_days }} 天</el-descriptions-item>
          <el-descriptions-item label="预测步长">{{ result.horizon }} 小时</el-descriptions-item>
          <el-descriptions-item label="回测折数">
            {{ result.folds }} 折
            <span class="text-muted" style="font-size: 12px">（每折 {{ result.valid_hours }} 小时）</span>
          </el-descriptions-item>
          <el-descriptions-item label="选型指标">
            {{ metricText(result.select_metric) }}
          </el-descriptions-item>
          <el-descriptions-item label="生成时间">
            {{ formatDateTime(result.generated_at, true) }}
          </el-descriptions-item>
          <el-descriptions-item label="批次号">
            <span class="mono">{{ result.batch_no }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- ------------------------------------------- 主图：历史 vs 预测 -->
      <div class="chart-card mb-16">
        <div class="chart-card__head">
          <div class="chart-card__title">历史实际需求 vs 未来预测需求</div>
          <span class="text-muted" style="font-size: 12px">
            实线=近 7 天实际，虚线=模型预测，可框选缩放
          </span>
        </div>
        <ChartBox
          :option="mainOption"
          :height="360"
          :loading="running"
          :empty="!lineData.labels.length"
          empty-text="暂无历史与预测数据"
          not-merge
        />
        <p class="chart-card__desc">
          阴影区间为基于回测残差标准差的近似 95% 置信区间（±1.96σ，并随预测步长线性放宽），
          区间越宽说明该时刻的不确定性越高，调度决策应保留更多冗余运力。
        </p>
      </div>

      <!-- -------------------------------------------- 模型对比表 + 柱状图 -->
      <el-row :gutter="14" class="mb-16">
        <el-col :xs="24" :md="14">
          <div class="chart-card">
            <div class="chart-card__head">
              <div class="chart-card__title">模型回测指标对比</div>
              <el-tag size="small" effect="plain" type="info">
                共 {{ result.metrics.length }} 个模型参与评估
              </el-tag>
            </div>
            <p class="chart-card__desc">
              主指标为 RMSE，对高峰时段误差更敏感；所有模型使用同一批滚动回测样本，指标可直接横向比较。
            </p>
            <el-table :data="result.metrics" size="small" border>
              <el-table-column label="模型" min-width="160">
                <template #default="{ row }">
                  <span>{{ row.model_label }}</span>
                  <el-tag v-if="row.is_best" type="success" size="small" effect="light" class="ml-4">
                    最优
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="MAE" align="right" width="100">
                <template #default="{ row }">
                  <span class="mono">{{ num(row.mae, 3) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="RMSE" align="right" width="100">
                <template #default="{ row }">
                  <span class="mono">{{ num(row.rmse, 3) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="MAPE(%)" align="right" width="110">
                <template #default="{ row }">
                  <span v-if="row.mape === null || row.mape === undefined" class="text-muted">—</span>
                  <span v-else class="mono">{{ num(row.mape, 2) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="R²" align="right" width="100">
                <template #default="{ row }">
                  <span v-if="row.r2 === null || row.r2 === undefined" class="text-muted">—</span>
                  <span v-else class="mono">{{ num(row.r2, 4) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <p class="chart-card__desc" style="margin-top: 10px">
              MAPE 在真实值接近 0 的深夜时段不稳定，可能为空；R² 反映拟合优度，越接近 1 越好。
            </p>
          </div>
        </el-col>

        <el-col :xs="24" :md="10">
          <div class="chart-card">
            <div class="chart-card__head">
              <div class="chart-card__title">各模型误差对比</div>
              <span class="text-muted" style="font-size: 12px">深色=最优模型</span>
            </div>
            <ChartBox
              :option="metricOption"
              :height="330"
              :loading="running"
              :empty="!result.metrics.length"
              empty-text="暂无模型指标"
            />
            <p class="chart-card__desc">
              柱越矮表示回测误差越小；MAE 反映平均偏差，RMSE 对大误差惩罚更重，两者差距大说明存在个别时段预测严重偏离。
            </p>
          </div>
        </el-col>
      </el-row>

      <!-- ------------------------------------------------------ 预测明细 -->
      <div class="chart-card mb-16">
        <div class="chart-card__head">
          <div class="chart-card__title">未来逐时预测明细</div>
          <el-tag size="small" effect="plain">共 {{ points.length }} 个时刻</el-tag>
        </div>
        <el-collapse v-model="activePanels">
          <el-collapse-item :title="`展开 / 收起未来 ${result.horizon} 小时预测明细表`" name="detail">
            <el-table :data="points" size="small" border max-height="360">
              <el-table-column label="时刻" min-width="150">
                <template #default="{ row }">
                  <span class="mono">{{ shortTime(row.time) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="预测需求量（单/小时）" align="right" min-width="170">
                <template #default="{ row }">
                  <span class="mono">{{ num(row.value, 1) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="置信下界" align="right" min-width="120">
                <template #default="{ row }">
                  <span class="mono text-muted">{{ num(row.lower, 1) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="置信上界" align="right" min-width="120">
                <template #default="{ row }">
                  <span class="mono text-muted">{{ num(row.upper, 1) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="区间宽度" align="right" min-width="120">
                <template #default="{ row }">
                  <span class="mono">{{ num(bandWidth(row), 1) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>

    <!-- -------------------------------------------- 准确率 + 历史批次 -->
    <el-row :gutter="14">
      <el-col :xs="24" :md="10">
        <div class="chart-card" v-loading="metaLoading">
          <div class="chart-card__head">
            <div class="chart-card__title">预测准确率评估</div>
            <el-tag size="small" type="info" effect="plain">近 30 天</el-tag>
          </div>
          <p class="chart-card__desc">
            准确率 = 100 − MAPE，仅统计「预测目标时刻已经发生」并回填了真实需求的样本。
          </p>
          <el-empty
            v-if="!accuracy.length"
            description="暂无可评估的预测样本（预测目标时刻尚未发生）"
            :image-size="70"
          />
          <el-table v-else :data="accuracy" size="small" border>
            <el-table-column label="模型" prop="model_label" min-width="150" />
            <el-table-column label="样本数" align="right" width="90">
              <template #default="{ row }">
                <span class="mono">{{ thousands(row.sample_count) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="MAE" align="right" width="90">
              <template #default="{ row }">
                <span class="mono">{{ num(row.mae, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="RMSE" align="right" width="90">
              <template #default="{ row }">
                <span class="mono">{{ num(row.rmse, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="MAPE(%)" align="right" width="100">
              <template #default="{ row }">
                <span v-if="row.mape === null || row.mape === undefined" class="text-muted">—</span>
                <span v-else class="mono">{{ num(row.mape, 2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="准确率" align="right" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.accuracy !== null && row.accuracy !== undefined" :type="accuracyTag(row.accuracy)" size="small" effect="light">
                  {{ num(row.accuracy, 2) }}%
                </el-tag>
                <span v-else class="text-muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :md="14">
        <div class="chart-card" v-loading="metaLoading">
          <div class="chart-card__head">
            <div class="chart-card__title">历史预测批次</div>
            <span class="text-muted" style="font-size: 12px">点击任意一行查看该批次逐时明细</span>
          </div>
          <p class="chart-card__desc">
            每次预测都会落库为独立批次，便于事后把预测值与真实需求对照，形成闭环评估。
          </p>
          <el-table
            :data="batches"
            size="small"
            border
            highlight-current-row
            class="clickable-table"
            empty-text="暂无历史预测批次"
            @row-click="openBatch"
          >
            <el-table-column label="批次号" min-width="180">
              <template #default="{ row }">
                <span class="mono">{{ row.batch_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="区域" prop="region_name" min-width="110" show-overflow-tooltip />
            <el-table-column label="模型" prop="model_label" min-width="130" show-overflow-tooltip />
            <el-table-column label="步长" align="right" width="80">
              <template #default="{ row }">{{ row.horizon }} h</template>
            </el-table-column>
            <el-table-column label="MAPE(%)" align="right" width="100">
              <template #default="{ row }">
                <span v-if="row.mape === null || row.mape === undefined" class="text-muted">—</span>
                <span v-else class="mono">{{ num(row.mape, 2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预测点数" align="right" width="100">
              <template #default="{ row }">
                <span class="mono">{{ row.point_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="生成时间" min-width="150">
              <template #default="{ row }">{{ formatDateTime(row.create_time, true) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <!-- ------------------------------------------------- 批次明细弹窗 -->
    <el-dialog v-model="batchVisible" :title="`预测批次明细 · ${batchNo}`" width="880px" top="6vh">
      <div v-loading="batchLoading">
        <p class="chart-card__desc" style="margin: 0 0 10px 0">
          「实际值」在目标时刻尚未发生时显示为「待观测」，偏差 = 实际值 − 预测值（正值表示实际需求高于预测）。
        </p>
        <el-table :data="batchRows" size="small" border max-height="460">
          <el-table-column label="目标时刻" min-width="150">
            <template #default="{ row }">
              <span class="mono">{{ formatDateTime(row.target_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="预测值" align="right" min-width="100">
            <template #default="{ row }">
              <span class="mono">{{ num(row.predicted_value, 1) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="下界" align="right" min-width="100">
            <template #default="{ row }">
              <span class="mono text-muted">{{ num(row.lower_bound, 1) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上界" align="right" min-width="100">
            <template #default="{ row }">
              <span class="mono text-muted">{{ num(row.upper_bound, 1) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="实际值" align="right" min-width="100">
            <template #default="{ row }">
              <span v-if="row.actual_value === null || row.actual_value === undefined" class="text-muted">
                待观测
              </span>
              <span v-else class="mono">{{ num(row.actual_value, 1) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="偏差" align="right" min-width="110">
            <template #default="{ row }">
              <span v-if="deviation(row) === null" class="text-muted">—</span>
              <span v-else class="mono" :class="deviationClass(row)">{{ signed(deviation(row), 1) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
/** 需求预测中心：滚动回测 → 自动选优 → 未来逐时需求预测与效果评估。 */
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { MagicStick, Refresh } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import ChartBox from '../components/ChartBox.vue';
import { forecastApi } from '../api';
import { formatDateTime, thousands } from '../utils/format';

const HORIZONS = [24, 48, 72];
/** 选型主指标的中文说明 */
const METRIC_TEXT = {
  rmse: 'RMSE 均方根误差',
  mae: 'MAE 平均绝对误差',
  mape: 'MAPE 平均绝对百分比误差',
};

const booting = ref(false);
const running = ref(false);
const metaLoading = ref(false);

const regions = ref([]);
const result = ref(null);
const accuracy = ref([]);
const batches = ref([]);
const activePanels = ref(['detail']);
const form = ref({ regionKey: 'all', horizon: 24, autoSelect: true });
/** 记录本次预测实际使用的参数，避免用户改动控件后与结果说明不一致 */
const runFlags = ref({ autoSelect: true });

const batchVisible = ref(false);
const batchLoading = ref(false);
const batchRows = ref([]);
const batchNo = ref('');

/* ------------------------------------------------------------------ 工具 */
function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function num(value, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—';
}

function signed(value, digits = 1) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '—';
  return `${parsed > 0 ? '+' : ''}${parsed.toFixed(digits)}`;
}

/** 后端返回 ISO 时间字符串，直接截取为 MM-DD HH:mm，避免时区解析差异 */
function shortTime(value) {
  if (!value) return '-';
  return String(value).replace('T', ' ').slice(5, 16);
}

function metricText(key) {
  return METRIC_TEXT[key] || key || '—';
}

function accuracyTag(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 'info';
  if (parsed >= 85) return 'success';
  if (parsed >= 70) return 'warning';
  return 'danger';
}

function deviation(row) {
  if (row.actual_value === null || row.actual_value === undefined) return null;
  return Number(row.actual_value) - Number(row.predicted_value);
}

/** 置信区间宽度；上下界缺失时返回 null */
function bandWidth(row) {
  const low = toNumber(row.lower);
  const high = toNumber(row.upper);
  if (low === null || high === null) return null;
  return Math.max(0, high - low);
}

function deviationClass(row) {
  const value = deviation(row);
  if (value === null) return '';
  const base = Math.max(Math.abs(Number(row.predicted_value)), 1);
  return Math.abs(value) / base > 0.25 ? 'text-warning' : '';
}

/* -------------------------------------------------------------- 数据加载 */
const points = computed(() => (result.value && result.value.points) || []);

async function loadRegions() {
  regions.value = await forecastApi.regions();
}

async function loadAccuracy() {
  accuracy.value = await forecastApi.accuracy({ days: 30 });
}

async function loadHistory() {
  batches.value = await forecastApi.history({ limit: 10 });
}

async function reloadMeta() {
  metaLoading.value = true;
  try {
    await Promise.all([loadRegions(), loadAccuracy(), loadHistory()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    metaLoading.value = false;
  }
}

async function runForecast() {
  running.value = true;
  try {
    const data = await forecastApi.run({
      region_id: form.value.regionKey === 'all' ? null : form.value.regionKey,
      horizon: form.value.horizon,
      auto_select: form.value.autoSelect,
    });
    result.value = data;
    runFlags.value = { autoSelect: form.value.autoSelect };
    activePanels.value = ['detail'];
    ElMessage.success(`预测完成：最优模型「${data.model_label}」，批次号 ${data.batch_no}`);
    await Promise.all([loadAccuracy(), loadHistory()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    running.value = false;
  }
}

async function openBatch(row) {
  if (!row || !row.batch_no) return;
  batchNo.value = row.batch_no;
  batchRows.value = [];
  batchVisible.value = true;
  batchLoading.value = true;
  try {
    batchRows.value = await forecastApi.batch(row.batch_no);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    batchLoading.value = false;
  }
}

/* ---------------------------------------------------------------- 图表 */
/**
 * 把「最近 7 天历史」与「未来 horizon 小时预测」拼到同一个类目轴上。
 * 置信区间用 stack 面积法实现：第一条 stack 系列放 lower，第二条放 upper - lower，
 * 两条系列都隐藏线宽与数据点，仅第二条绘制浅色面积，从而形成一条上下界之间的带子。
 */
const lineData = computed(() => {
  const history = (result.value && result.value.history) || [];
  const future = (result.value && result.value.points) || [];
  const labels = [
    ...history.map((item) => shortTime(item.time)),
    ...future.map((item) => shortTime(item.time)),
  ];
  const historyValues = [
    ...history.map((item) => toNumber(item.value)),
    ...future.map(() => null),
  ];
  const predictValues = [
    ...history.map(() => null),
    ...future.map((item) => toNumber(item.value)),
  ];
  // 让虚线从最后一个历史点起笔，视觉上与实线衔接
  if (history.length && future.length) {
    predictValues[history.length - 1] = toNumber(history[history.length - 1].value);
  }
  const bandBase = [
    ...history.map(() => null),
    ...future.map((item) => toNumber(item.lower)),
  ];
  const bandSpan = [
    ...history.map(() => null),
    ...future.map((item) => {
      const low = toNumber(item.lower);
      const high = toNumber(item.upper);
      if (low === null || high === null) return null;
      return Math.max(0, high - low);
    }),
  ];
  return { history, future, labels, historyValues, predictValues, bandBase, bandSpan };
});

function mainTooltip(params) {
  if (!params || !params.length) return '';
  const index = params[0].dataIndex;
  const data = lineData.value;
  const rows = [`<div style="font-weight:600;margin-bottom:4px">${data.labels[index] || ''}</div>`];
  const historyValue = data.historyValues[index];
  if (historyValue !== null && historyValue !== undefined) {
    rows.push(`<div>历史实际需求：<b>${historyValue}</b> 单</div>`);
  }
  if (index >= data.history.length) {
    const point = data.future[index - data.history.length];
    if (point) {
      rows.push(`<div>预测需求：<b style="color:#2b6de5">${num(point.value, 1)}</b> 单</div>`);
      rows.push(
        `<div style="color:#6b7280">95% 置信区间：${num(point.lower, 1)} ~ ${num(point.upper, 1)}</div>`
      );
    }
  }
  return rows.join('');
}

const mainOption = computed(() => {
  const data = lineData.value;
  const total = data.labels.length;
  const labelInterval = total > 24 ? Math.max(0, Math.ceil(total / 12) - 1) : 0;
  const lastHistory = data.history.length ? data.history[data.history.length - 1] : null;
  const splitLabel = lastHistory ? shortTime(lastHistory.time) : '';
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: '#2b6de5' } },
      formatter: mainTooltip,
    },
    legend: { data: ['历史实际需求', '预测需求', '95% 置信区间'], right: 0, top: 0 },
    grid: { left: 10, right: 20, top: 44, bottom: 54, containLabel: true },
    dataZoom: [
      { type: 'inside', throttle: 50 },
      {
        type: 'slider',
        height: 16,
        bottom: 6,
        borderColor: 'transparent',
        fillerColor: 'rgba(43,109,229,0.10)',
        handleStyle: { color: '#2b6de5' },
        textStyle: { color: '#6b7280', fontSize: 10 },
      },
    ],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.labels,
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisLabel: { color: '#6b7280', fontSize: 11, interval: labelInterval },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '需求(单/小时)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: '区间下界',
        type: 'line',
        stack: 'confidence',
        symbol: 'none',
        silent: true,
        data: data.bandBase,
        lineStyle: { opacity: 0 },
        itemStyle: { opacity: 0 },
        areaStyle: { opacity: 0 },
      },
      {
        name: '95% 置信区间',
        type: 'line',
        stack: 'confidence',
        symbol: 'none',
        silent: true,
        data: data.bandSpan,
        lineStyle: { opacity: 0 },
        itemStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(43,109,229,0.16)', opacity: 1 },
      },
      {
        name: '历史实际需求',
        type: 'line',
        symbol: 'none',
        data: data.historyValues,
        itemStyle: { color: '#94a3b8' },
        lineStyle: { width: 2, color: '#94a3b8' },
      },
      {
        name: '预测需求',
        type: 'line',
        symbol: 'none',
        data: data.predictValues,
        itemStyle: { color: '#2b6de5' },
        lineStyle: { width: 2.4, type: 'dashed', color: '#2b6de5' },
        markLine: splitLabel
          ? {
              silent: true,
              symbol: 'none',
              lineStyle: { type: 'dashed', color: '#94a3b8' },
              label: { formatter: '预测起点', color: '#6b7280', fontSize: 11 },
              data: [{ xAxis: splitLabel }],
            }
          : undefined,
      },
    ],
  };
});

const metricOption = computed(() => {
  const list = (result.value && result.value.metrics) || [];
  const bar = (key, bestColor, normalColor) =>
    list.map((item) => ({
      value: toNumber(item[key]),
      itemStyle: item.is_best
        ? { color: bestColor, borderRadius: [4, 4, 0, 0] }
        : { color: normalColor, borderRadius: [4, 4, 0, 0] },
    }));
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['MAE', 'RMSE'], right: 0, top: 0 },
    grid: { left: 10, right: 14, top: 44, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((item) => item.model_label),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7280',
        fontSize: 10,
        interval: 0,
        rotate: list.length > 4 ? 30 : 0,
        width: 76,
        overflow: 'truncate',
      },
    },
    yAxis: {
      type: 'value',
      name: '误差(单/小时)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f4f9' } },
      axisLabel: { color: '#6b7280' },
    },
    series: [
      {
        name: 'MAE',
        type: 'bar',
        barMaxWidth: 22,
        data: bar('mae', '#2b6de5', 'rgba(43,109,229,0.40)'),
      },
      {
        name: 'RMSE',
        type: 'bar',
        barMaxWidth: 22,
        data: bar('rmse', '#06b6d4', 'rgba(6,182,212,0.38)'),
      },
    ],
  };
});

onMounted(async () => {
  booting.value = true;
  try {
    await Promise.all([loadRegions(), loadAccuracy(), loadHistory()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    booting.value = false;
  }
  // 首次进入自动执行「全域 + 未来 24 小时」预测
  runForecast();
});
</script>

<style scoped>
.filter-label {
  font-size: 13px;
  color: var(--app-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.tip-icon {
  cursor: help;
  font-size: 13px;
  color: #b8c0cc;
}
.hint {
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.option-extra {
  float: right;
  font-size: 12px;
  margin-left: 16px;
}
.ml-4 {
  margin-left: 4px;
}
.clickable-table :deep(.el-table__row) {
  cursor: pointer;
}
:deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}
</style>
