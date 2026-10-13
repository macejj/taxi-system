<template>
  <div v-loading="loading">
    <PageHeader
      title="运营区域管理"
      description="区域是需求分析与调度决策的空间基本单元（城市功能区网格），维护区域编码、功能区类型、中心坐标与需求强度，直接影响供需缺口测算结果。"
    >
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增区域</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 区域统计 -->
    <el-row :gutter="14" class="mb-16">
      <el-col v-for="card in statCards" :key="card.label" :xs="12" :sm="12" :md="6" :lg="6">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="区域名称 / 编码"
        clearable
        style="width: 200px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="query.region_type"
        placeholder="功能区类型"
        clearable
        filterable
        style="width: 160px"
        @change="handleSearch"
      >
        <el-option v-for="item in typeOptions" :key="item" :label="item" :value="item" />
      </el-select>

      <el-select
        v-model="query.status"
        placeholder="启用状态"
        clearable
        style="width: 130px"
        @change="handleSearch"
      >
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>

      <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
    </div>

    <!-- 区域列表 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div class="chart-card__title">
          区域清单
          <span class="text-muted" style="font-size: 12px; font-weight: 400">
            共 {{ total }} 个
          </span>
        </div>
        <span class="text-muted" style="font-size: 12px">
          需求强度 1-5 级用于预测与调度时的需求权重，等级越高表示该区域叫车需求越集中
        </span>
      </div>

      <el-table :data="list" row-key="id" border stripe style="width: 100%">
        <el-table-column prop="code" label="区域编码" width="120" fixed="left">
          <template #default="{ row }">
            <span class="mono">{{ row.code }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="区域名称" min-width="150" show-overflow-tooltip />

        <el-table-column prop="region_type" label="功能区类型" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.region_type)" size="small" effect="light">
              {{ row.region_type || '未分类' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="中心坐标(经度, 纬度)" width="210">
          <template #default="{ row }">
            <span class="mono">{{ coordText(row) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="area_km2" label="面积(km²)" width="120" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.area_km2, 2) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="demand_level" label="需求强度" width="180">
          <template #default="{ row }">
            <div class="rate-cell">
              <el-rate :model-value="Number(row.demand_level) || 0" disabled size="small" />
              <span class="mono text-muted">{{ demandLevelText(row.demand_level) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusInfo(row.status).type" size="small" effect="light">
              {{ statusInfo(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="row.remark ? '' : 'text-muted'">{{ row.remark || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="130" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无区域数据，可点击右上角「新增区域」创建功能区网格" :image-size="80" />
        </template>
      </el-table>

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
    </div>

    <!-- 新增 / 编辑区域 -->
    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑区域' : '新增区域'"
      width="680px"
      top="7vh"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="14">
          <el-col :xs="24" :md="12">
            <el-form-item label="区域编码" prop="code">
              <el-input v-model="form.code" maxlength="20" placeholder="如 R001" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="区域名称" prop="name">
              <el-input v-model="form.name" maxlength="50" placeholder="如 火车站枢纽片区" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="功能区类型" prop="region_type">
              <el-select
                v-model="form.region_type"
                placeholder="选择或直接输入新类型"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option v-for="item in typeOptions" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="启用状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio :value="1">启用</el-radio>
                <el-radio :value="0">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="中心经度" prop="center_lng">
              <el-input-number
                v-model="form.center_lng"
                :min="-180"
                :max="180"
                :precision="6"
                :step="0.01"
                :controls="false"
                placeholder="如 120.123456"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="中心纬度" prop="center_lat">
              <el-input-number
                v-model="form.center_lat"
                :min="-90"
                :max="90"
                :precision="6"
                :step="0.01"
                :controls="false"
                placeholder="如 30.123456"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="面积(km²)" prop="area_km2">
              <el-input-number
                v-model="form.area_km2"
                :min="0"
                :max="9999"
                :precision="2"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="需求强度" prop="demand_level">
              <el-slider
                v-model="form.demand_level"
                :min="1"
                :max="5"
                :step="1"
                show-stops
                :marks="demandMarks"
              />
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input
                v-model="form.remark"
                type="textarea"
                :rows="2"
                maxlength="200"
                show-word-limit
                placeholder="如 覆盖范围说明、主要客流特征等"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import { regionApi } from '../api';
import { thousands } from '../utils/format';

/** 区域启用状态字典（format.js 未提供，本页局部定义）。 */
const REGION_STATUS = {
  0: { text: '停用', type: 'info' },
  1: { text: '启用', type: 'success' },
};

/** 标签配色池：按功能区类型在选项中的位置取色，新增类型也能稳定着色。 */
const TAG_PALETTE = ['primary', 'success', 'warning', 'danger', 'info'];

/** 无数据时 types() 可能返回较少类型，这里补齐常用功能区类型，保证下拉可用。 */
const DEFAULT_REGION_TYPES = ['交通枢纽', '商圈', '居民区', '学校', '景区', '医院', '工业区'];

const DEMAND_LEVEL_TEXT = {
  1: '很低',
  2: '较低',
  3: '中等',
  4: '较高',
  5: '很高',
};

const loading = ref(false);
const saving = ref(false);
const list = ref([]);
const total = ref(0);
const typeOptionsRaw = ref([]);
const stats = ref({ total: 0, enabled: 0, disabled: 0, area: 0 });

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  region_type: null,
  status: null,
});

const typeOptions = computed(() => {
  const merged = [...typeOptionsRaw.value];
  DEFAULT_REGION_TYPES.forEach((item) => {
    if (!merged.includes(item)) merged.push(item);
  });
  return merged;
});

const statCards = computed(() => [
  {
    label: '区域总数',
    value: stats.value.total,
    unit: '个',
    icon: 'MapLocation',
    tone: 'blue',
    sub: `功能区类型 ${typeOptions.value.length} 类`,
  },
  {
    label: '启用区域',
    value: stats.value.enabled,
    unit: '个',
    icon: 'CircleCheck',
    tone: 'green',
    sub: '参与需求分析与调度',
  },
  {
    label: '停用区域',
    value: stats.value.disabled,
    unit: '个',
    icon: 'CircleClose',
    tone: 'orange',
    sub: '不参与缺口测算',
  },
  {
    label: '覆盖面积合计',
    value: stats.value.area,
    unit: 'km²',
    icon: 'Grid',
    tone: 'cyan',
    digits: 2,
    sub: '按当前全部区域统计',
  },
]);

/* ------------------------------------------------------------ 数据加载 */

function buildParams() {
  const params = { page: query.page, page_size: query.page_size };
  if (query.keyword && query.keyword.trim()) params.keyword = query.keyword.trim();
  if (query.region_type) params.region_type = query.region_type;
  if (query.status !== null && query.status !== undefined && query.status !== '') {
    params.status = query.status;
  }
  return params;
}

async function load() {
  loading.value = true;
  try {
    const data = await regionApi.page(buildParams());
    list.value = data.items || [];
    total.value = data.total || 0;
  } catch (error) {
    // 拦截器已统一提示，这里只保证页面处于空态
    list.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

/**
 * 区域统计：启用/停用数量用单条分页请求的 total；
 * 覆盖面积合计后端未提供汇总接口，改为一次取最多 500 条在前端累加
 * （区域数量通常远小于 500，若超出则该面积合计会被低估）。
 */
async function loadStats() {
  try {
    const [all, enabled, disabled] = await Promise.all([
      regionApi.page({ page: 1, page_size: 500 }),
      regionApi.page({ page: 1, page_size: 1, status: 1 }),
      regionApi.page({ page: 1, page_size: 1, status: 0 }),
    ]);
    const items = all.items || [];
    stats.value = {
      total: all.total || 0,
      enabled: enabled.total || 0,
      disabled: disabled.total || 0,
      area: items.reduce((sum, item) => sum + (Number(item.area_km2) || 0), 0),
    };
  } catch (error) {
    // 拦截器已统一提示
  }
}

async function loadTypes() {
  try {
    typeOptionsRaw.value = (await regionApi.types()) || [];
  } catch (error) {
    // 拦截器已统一提示
  }
}

async function loadAll() {
  await Promise.all([load(), loadStats()]);
}

function handleSearch() {
  query.page = 1;
  load();
}

function resetQuery() {
  query.page = 1;
  query.keyword = '';
  query.region_type = null;
  query.status = null;
  load();
}

/* ------------------------------------------------------------ 展示辅助 */

function statusInfo(status) {
  return REGION_STATUS[status] || { text: '未知', type: 'info' };
}

function typeTagType(regionType) {
  const index = typeOptions.value.indexOf(regionType);
  if (index < 0) return 'info';
  return TAG_PALETTE[index % TAG_PALETTE.length];
}

function demandLevelText(level) {
  return DEMAND_LEVEL_TEXT[level] || '未评级';
}

/** 中心坐标缺失时显示占位符，避免出现 (null, null)。 */
function coordText(row) {
  const hasLng = row.center_lng !== null && row.center_lng !== undefined;
  const hasLat = row.center_lat !== null && row.center_lat !== undefined;
  if (!hasLng && !hasLat) return '—';
  const lng = hasLng ? thousands(row.center_lng, 6) : '—';
  const lat = hasLat ? thousands(row.center_lat, 6) : '—';
  return `(${lng}, ${lat})`;
}

/* ------------------------------------------------------------ 新增 / 编辑 */

const dialogVisible = ref(false);
const formRef = ref(null);
const demandMarks = { 1: '低', 3: '中', 5: '高' };

function emptyForm() {
  return {
    id: null,
    code: '',
    name: '',
    region_type: '居民区',
    center_lng: null,
    center_lat: null,
    area_km2: 10,
    demand_level: 3,
    status: 1,
    remark: '',
  };
}

const form = reactive(emptyForm());

const rules = {
  code: [
    { required: true, message: '请输入区域编码', trigger: 'blur' },
    { max: 20, message: '区域编码不超过 20 个字符', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入区域名称', trigger: 'blur' },
    { max: 50, message: '区域名称不超过 50 个字符', trigger: 'blur' },
  ],
  region_type: [{ required: true, message: '请选择或输入功能区类型', trigger: 'change' }],
};

function assignForm(source) {
  const target = emptyForm();
  Object.keys(target).forEach((key) => {
    if (source[key] !== undefined && source[key] !== null) target[key] = source[key];
  });
  Object.assign(form, target);
}

function openCreate() {
  assignForm(emptyForm());
  dialogVisible.value = true;
}

function openEdit(row) {
  assignForm(row);
  dialogVisible.value = true;
}

function buildPayload() {
  return {
    code: form.code,
    name: form.name,
    region_type: form.region_type,
    center_lng: form.center_lng ?? null,
    center_lat: form.center_lat ?? null,
    area_km2: form.area_km2 ?? null,
    demand_level: form.demand_level ?? 3,
    status: form.status ?? 1,
    remark: form.remark || null,
  };
}

async function submitForm() {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
  } catch (error) {
    return; // 表单校验未通过，交由 el-form 提示
  }
  saving.value = true;
  const editing = Boolean(form.id);
  try {
    if (editing) {
      await regionApi.update(form.id, buildPayload());
    } else {
      await regionApi.create(buildPayload());
    }
    ElMessage.success(editing ? '区域信息已保存' : '区域已新增');
    dialogVisible.value = false;
    await Promise.all([loadAll(), loadTypes()]);
  } catch (error) {
    // 拦截器已统一提示（如区域编码已存在）
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除区域「${row.name}」吗？删除后不可恢复；若该区域已产生营运记录或叫车需求，请改为「停用」。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    );
  } catch (error) {
    return; // 用户取消
  }
  try {
    await regionApi.remove(row.id);
    ElMessage.success('区域已删除');
    await Promise.all([loadAll(), loadTypes()]);
  } catch (error) {
    // 区域存在关联的营运记录或叫车需求时后端返回 400，
    // 错误提示由 request 拦截器统一弹出（提示改为「停用」），此处无需重复提示。
  }
}

onMounted(async () => {
  await loadTypes();
  await loadAll();
});
</script>

<style scoped>
.rate-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.rate-cell :deep(.el-rate) {
  height: auto;
  line-height: 1;
}
:deep(.el-table .cell) {
  word-break: break-word;
}
</style>
