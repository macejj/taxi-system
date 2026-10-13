<template>
  <div v-loading="loading">
    <PageHeader
      title="数据维护"
      description="查看各业务表的数据规模与数据健康度、一键生成可复现的演示数据，以及清理业务数据。本页操作仅系统管理员可用。"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 数据量统计 -->
    <div class="chart-card mb-16">
      <div class="chart-card__head">
        <div class="chart-card__title">数据量统计</div>
        <span class="text-muted" style="font-size: 12px">
          业务数据合计 {{ thousands(totalRecords) }} 条
        </span>
      </div>
      <div class="chart-card__desc">
        统计各业务表的记录数，用于判断当前数据规模是否满足分析、建模与答辩演示的需要。
      </div>
      <el-row :gutter="12">
        <el-col v-for="item in statCards" :key="item.key" :xs="12" :sm="8" :md="6" :lg="4">
          <StatCard
            v-bind="item"
            unit="条"
            class="mb-16"
            :value="stats[item.key] || 0"
          />
        </el-col>
      </el-row>
    </div>

    <!-- 数据健康度 -->
    <div class="chart-card mb-16">
      <div class="chart-card__head">
        <div class="chart-card__title">数据健康度</div>
        <el-tag :type="readyForForecast ? 'success' : 'warning'" effect="light">
          {{ readyForForecast ? '满足建模条件' : '数据不足' }}
        </el-tag>
      </div>
      <div class="chart-card__desc">
        需求预测需要足够的连续历史数据；历史天数与叫车需求数量直接决定模型能否训练与回测。
      </div>

      <el-descriptions :column="4" size="small" border>
        <el-descriptions-item label="数据时间范围">{{ rangeText }}</el-descriptions-item>
        <el-descriptions-item label="历史天数">
          <span class="mono">{{ historyDays }}</span> 天
        </el-descriptions-item>
        <el-descriptions-item label="最新叫车需求">
          {{ formatDateTime(health.latest_request_time, true) }}
        </el-descriptions-item>
        <el-descriptions-item label="最新营运订单">
          {{ formatDateTime(health.latest_order_time, true) }}
        </el-descriptions-item>
        <el-descriptions-item label="叫车需求数">
          {{ thousands(health.counts?.ride_request) }}
        </el-descriptions-item>
        <el-descriptions-item label="营运订单数">
          {{ thousands(orderCount) }}
        </el-descriptions-item>
        <el-descriptions-item label="调度方案数">
          {{ thousands(health.counts?.dispatch_plan) }}
        </el-descriptions-item>
        <el-descriptions-item label="预测结果数">
          {{ thousands(health.counts?.forecast_result) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        class="mt-16"
        :type="readyForForecast ? 'success' : 'warning'"
        :closable="false"
        show-icon
        :title="
          readyForForecast
            ? `历史天数 ${historyDays} 天，已满足需求预测的建模条件（≥ 14 天）。`
            : `历史天数 ${historyDays} 天，历史天数 ≥ 14 天才能使用需求预测功能。`
        "
      />

      <el-alert
        v-if="needData"
        class="mt-16"
        type="error"
        :closable="false"
        show-icon
        title="当前系统还没有任何营运数据，运营分析、需求预测与调度决策都无法使用！"
      >
        <template #default>
          <div style="font-size: 12.5px; line-height: 1.8">
            请在下方的「生成仿真数据」中一键生成演示数据（含区域、车辆、驾驶员、人车绑定、逐小时叫车需求与营运订单）。
          </div>
          <el-button type="primary" size="small" class="mt-16" @click="scrollToSimulate">
            立即前往生成演示数据
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 生成仿真数据 -->
    <div ref="simulateRef" class="chart-card mb-16">
      <div class="chart-card__head">
        <div class="chart-card__title">生成仿真数据</div>
        <el-tag v-if="simulating" type="warning" effect="dark">
          生成中，已用时 {{ elapsed }} 秒
        </el-tag>
      </div>
      <div class="chart-card__desc">
        生成的数据包含「区域、车辆、驾驶员、人车绑定、逐小时叫车需求与营运订单」，含日周期、周周期、天气与节假日因子，同一随机种子结果可复现。
      </div>

      <el-alert
        class="mb-16"
        type="warning"
        :closable="false"
        show-icon
        title="勾选「先清空现有业务数据」会删除现有全部业务数据（营运订单、叫车需求、人车绑定、调度方案与预测结果），删除后不可恢复！"
      />

      <el-form :model="simForm" label-width="180px" :disabled="simulating" @submit.prevent>
        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <el-form-item label="生成天数">
              <el-input-number v-model="simForm.days" :min="7" :max="365" :step="1" style="width: 200px" />
              <span class="text-muted" style="margin-left: 10px; font-size: 12px">7~365 天</span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="车辆数">
              <el-input-number v-model="simForm.vehicles" :min="5" :max="500" :step="5" style="width: 200px" />
              <span class="text-muted" style="margin-left: 10px; font-size: 12px">5~500 台</span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="驾驶员数">
              <el-input-number v-model="simForm.drivers" :min="5" :max="800" :step="5" style="width: 200px" />
              <span class="text-muted" style="margin-left: 10px; font-size: 12px">5~800 人</span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="随机种子">
              <el-input-number v-model="simForm.seed" :min="1" :step="1" style="width: 200px" />
              <span class="text-muted" style="margin-left: 10px; font-size: 12px">
                相同种子结果可复现
              </span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="先清空现有业务数据">
              <el-switch v-model="simForm.reset" active-text="是" inactive-text="否" />
              <span class="text-muted" style="margin-left: 10px; font-size: 12px">
                勾选后将删除现有业务数据
              </span>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-alert
        v-if="simulating"
        type="info"
        :closable="false"
        show-icon
        title="数据生成约需 1~3 分钟，请勿关闭页面或刷新浏览器。"
        class="mb-16"
      >
        <template #default>
          <el-progress
            :percentage="100"
            :indeterminate="true"
            :duration="2"
            :show-text="false"
            :stroke-width="10"
            style="margin-top: 8px"
          />
          <div class="text-muted" style="font-size: 12px; margin-top: 6px">
            正在按日生成逐小时叫车需求与营运订单，已用时 {{ elapsed }} 秒，请耐心等待……
          </div>
        </template>
      </el-alert>

      <el-tooltip :disabled="isAdmin" content="仅系统管理员可生成仿真数据" placement="top">
        <span>
          <el-button
            type="primary"
            :icon="MagicStick"
            :loading="simulating"
            :disabled="!isAdmin"
            @click="startSimulate"
          >
            {{ simulating ? '正在生成数据…' : '开始生成' }}
          </el-button>
        </span>
      </el-tooltip>
      <span class="text-muted" style="margin-left: 12px; font-size: 12px">
        生成前会二次确认，历史天数 ≥ 14 天后即可使用需求预测功能。
      </span>
    </div>

    <!-- 清理数据 -->
    <div class="chart-card">
      <div class="chart-card__head">
        <div class="chart-card__title">清理数据</div>
        <el-tag v-if="!isAdmin" type="info" effect="plain">
          当前角色（{{ ROLE_TEXT[currentUser.role] || currentUser.role || '-' }}）仅可查看
        </el-tag>
      </div>
      <div class="chart-card__desc">
        清空操作不可恢复，执行前请确认需要保留的数据已导出备份。清理后数据量统计会自动刷新。
      </div>

      <el-tooltip :disabled="isAdmin" content="仅系统管理员可清理数据" placement="top">
        <span>
          <el-button
            type="warning"
            plain
            :icon="Delete"
            :loading="clearingBusiness"
            :disabled="!isAdmin || clearingAll"
            @click="clearBusinessData"
          >
            清空业务数据（保留基础档案）
          </el-button>
        </span>
      </el-tooltip>
      <span class="text-muted" style="margin-left: 12px; font-size: 12px">
        仅删除营运订单、叫车需求、人车绑定、调度方案/调度单与预测结果
      </span>

      <el-divider style="margin: 14px 0" />

      <el-tooltip :disabled="isAdmin" content="仅系统管理员可清理数据" placement="top">
        <span>
          <el-button
            type="danger"
            :icon="Delete"
            :loading="clearingAll"
            :disabled="!isAdmin || clearingBusiness"
            @click="clearAllData"
          >
            清空全部数据（含车辆/驾驶员/区域）
          </el-button>
        </span>
      </el-tooltip>
      <span class="text-muted" style="margin-left: 12px; font-size: 12px">
        需输入确认词 DELETE，执行后系统回到初始空库状态
      </span>
    </div>

    <!-- 生成结果 -->
    <el-dialog
      v-model="resultVisible"
      title="数据生成完成"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-result icon="success" title="仿真数据已生成" :sub-title="resultSummary" />
      <el-descriptions :column="2" size="small" border>
        <el-descriptions-item label="区域数">{{ thousands(result.regions) }}</el-descriptions-item>
        <el-descriptions-item label="车辆数">{{ thousands(result.vehicles) }}</el-descriptions-item>
        <el-descriptions-item label="驾驶员数">{{ thousands(result.drivers) }}</el-descriptions-item>
        <el-descriptions-item label="人车绑定数">{{ thousands(result.bindings) }}</el-descriptions-item>
        <el-descriptions-item label="叫车需求数">{{ thousands(result.requests) }}</el-descriptions-item>
        <el-descriptions-item label="营运订单数">{{ thousands(result.operations) }}</el-descriptions-item>
        <el-descriptions-item label="生成耗时">{{ result.seconds ?? 0 }} 秒</el-descriptions-item>
        <el-descriptions-item label="随机种子">{{ simForm.seed }}</el-descriptions-item>
      </el-descriptions>
      <div class="text-muted mt-16" style="font-size: 12.5px">
        数据已生成，可前往『运营驾驶舱』查看；历史天数达到 14 天后即可使用需求预测功能。
      </div>
      <template #footer>
        <el-button @click="resultVisible = false">留在本页</el-button>
        <el-button type="primary" @click="goDashboard">前往『运营驾驶舱』</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Delete, MagicStick, Refresh } from '@element-plus/icons-vue';
import PageHeader from '../../components/PageHeader.vue';
import StatCard from '../../components/StatCard.vue';
import { authApi, dashboardApi, systemApi } from '../../api';
import { ROLE_TEXT, duration, formatDate, formatDateTime, thousands } from '../../utils/format';

const router = useRouter();

const loading = ref(false);
const stats = ref({});
const health = ref({});
const currentUser = ref({});
const simulateRef = ref(null);

const simulating = ref(false);
const elapsed = ref(0);
const resultVisible = ref(false);
const result = ref({});

const clearingBusiness = ref(false);
const clearingAll = ref(false);

const simForm = ref({ days: 60, vehicles: 60, drivers: 80, seed: 20240501, reset: true });

let timer = null;

/** 12 项数据量统计（后端 dataStats 返回的表） */
const statCards = [
  { key: 'region', label: '运营区域', icon: 'MapLocation', tone: 'blue' },
  { key: 'vehicle', label: '车辆', icon: 'Van', tone: 'green' },
  { key: 'driver', label: '驾驶员', icon: 'UserFilled', tone: 'purple' },
  { key: 'vehicle_driver', label: '人车绑定', icon: 'Connection', tone: 'cyan' },
  { key: 'ride_request', label: '叫车需求', icon: 'DataLine', tone: 'orange' },
  { key: 'operation_record', label: '营运订单', icon: 'Tickets', tone: 'blue' },
  { key: 'dispatch_plan', label: '调度方案', icon: 'Guide', tone: 'purple' },
  { key: 'dispatch_order', label: '调度单', icon: 'Promotion', tone: 'cyan' },
  { key: 'forecast_result', label: '预测结果', icon: 'MagicStick', tone: 'green' },
  { key: 'sys_user', label: '系统用户', icon: 'User', tone: 'orange' },
  { key: 'operation_log', label: '操作日志', icon: 'Document', tone: 'red' },
];

const isAdmin = computed(() => currentUser.value.role === 'admin');
const historyDays = computed(() => health.value.history_days || 0);
const readyForForecast = computed(() => Boolean(health.value.ready_for_forecast));
const orderCount = computed(
  () => health.value.counts?.operation_record ?? stats.value.operation_record ?? 0
);
/** 无任何营运数据时给出醒目引导 */
const needData = computed(() => !readyForForecast.value && orderCount.value === 0);

const totalRecords = computed(() =>
  statCards.reduce((sum, item) => sum + (Number(stats.value[item.key]) || 0), 0)
);

/** 由最新订单时间与历史天数推算数据时间范围 */
const rangeText = computed(() => {
  const latest = health.value.latest_order_time;
  if (!latest) return '暂无数据';
  const days = historyDays.value > 0 ? historyDays.value : 1;
  const start = new Date(new Date(latest).getTime() - (days - 1) * 24 * 3600 * 1000);
  return `${formatDate(start)} ~ ${formatDate(latest)}（${days} 天）`;
});

/** 生成结果标题：耗时超过 1 分钟时附带可读时长 */
const resultSummary = computed(() => {
  const seconds = Number(result.value.seconds) || 0;
  return seconds >= 60 ? `共耗时 ${seconds} 秒（约 ${duration(seconds)}）` : `共耗时 ${seconds} 秒`;
});

function startTimer() {
  elapsed.value = 0;
  stopTimer();
  timer = setInterval(() => {
    elapsed.value += 1;
  }, 1000);
}

function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

async function loadStats() {
  stats.value = await systemApi.dataStats();
}

async function loadHealth() {
  health.value = await dashboardApi.health();
}

async function loadCurrentUser() {
  try {
    currentUser.value = await authApi.me();
  } catch (error) {
    /* 拦截器已提示 */
  }
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadStats(), loadHealth()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}

function scrollToSimulate() {
  if (simulateRef.value) {
    simulateRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function goDashboard() {
  resultVisible.value = false;
  router.push('/dashboard');
}

async function startSimulate() {
  const form = simForm.value;
  try {
    await ElMessageBox.confirm(
      form.reset
        ? `将先清空现有全部业务数据，再生成最近 ${form.days} 天的仿真数据（车辆 ${form.vehicles} 台、驾驶员 ${form.drivers} 人、种子 ${form.seed}）。现有数据删除后不可恢复，确定继续吗？`
        : `将保留现有数据，追加生成最近 ${form.days} 天的仿真数据（车辆 ${form.vehicles} 台、驾驶员 ${form.drivers} 人、种子 ${form.seed}）。数据生成期间请勿关闭页面，确定继续吗？`,
      '生成仿真数据',
      form.reset
        ? { type: 'warning', confirmButtonText: '确定生成', cancelButtonText: '取消' }
        : { type: 'info', confirmButtonText: '确定生成', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }

  simulating.value = true;
  startTimer();
  try {
    const data = await systemApi.simulate({
      days: form.days,
      vehicles: form.vehicles,
      drivers: form.drivers,
      seed: form.seed,
      reset: form.reset,
    });
    result.value = data || {};
    resultVisible.value = true;
    ElMessage.success(data?.message || '仿真数据生成完成');
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    simulating.value = false;
    stopTimer();
  }
}

async function clearBusinessData() {
  try {
    await ElMessageBox.confirm(
      '将删除全部营运订单、叫车需求、人车绑定、调度方案/调度单与预测结果，保留车辆、驾驶员、区域等基础档案。清空后不可恢复，确定继续吗？',
      '清空业务数据',
      { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }
  clearingBusiness.value = true;
  try {
    const data = await systemApi.clearData({ include_master: false });
    ElMessage.success(data?.message || '业务数据已清空');
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    clearingBusiness.value = false;
  }
}

async function clearAllData() {
  try {
    await ElMessageBox.confirm(
      '将同时删除车辆、驾驶员、区域等基础档案以及全部业务流水，系统回到初始空库状态；操作日志与系统用户会保留。此操作不可恢复，确定继续吗？',
      '清空全部数据',
      { type: 'error', confirmButtonText: '继续', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }
  try {
    await ElMessageBox.prompt('该操作将清空全部数据且不可恢复，请输入确认词 DELETE 后继续。', '危险操作确认', {
      confirmButtonText: '确定清空',
      cancelButtonText: '取消',
      inputPlaceholder: 'DELETE',
      inputValidator: (value) => (value === 'DELETE' ? true : '确认词不正确，请输入 DELETE'),
    });
  } catch (error) {
    return;
  }
  clearingAll.value = true;
  try {
    const data = await systemApi.clearData({ include_master: true });
    ElMessage.success(data?.message || '全部数据已清空');
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    clearingAll.value = false;
  }
}

onMounted(async () => {
  await loadCurrentUser();
  loadAll();
});

onBeforeUnmount(stopTimer);
</script>

<style scoped>
.chart-card :deep(.el-descriptions) {
  margin-bottom: 2px;
}
</style>
