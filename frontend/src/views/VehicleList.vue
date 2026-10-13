<template>
  <div v-loading="loading">
    <PageHeader
      title="车辆管理"
      description="维护营运车辆档案（车牌、品牌型号、类型、能源、常驻区域与证照信息），并对保险、营运证、保养到期情况给出提醒。"
    >
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增车辆</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 车队统计 -->
    <el-row :gutter="14" class="mb-16">
      <el-col v-for="card in statCards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="车牌号 / 品牌型号"
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
        v-model="query.status"
        placeholder="车辆状态"
        clearable
        style="width: 130px"
        @change="handleSearch"
      >
        <el-option label="在营" :value="1" />
        <el-option label="停运" :value="0" />
        <el-option label="维修" :value="2" />
      </el-select>

      <el-select
        v-model="query.home_region_id"
        placeholder="常驻区域"
        clearable
        filterable
        style="width: 160px"
        @change="handleSearch"
      >
        <el-option v-for="item in regions" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>

      <el-select
        v-model="query.vehicle_type"
        placeholder="车辆类型"
        clearable
        style="width: 150px"
        @change="handleSearch"
      >
        <el-option
          v-for="item in dictionaries.vehicle_type"
          :key="item"
          :label="item"
          :value="item"
        />
      </el-select>

      <el-select
        v-model="query.energy_type"
        placeholder="能源类型"
        clearable
        style="width: 130px"
        @change="handleSearch"
      >
        <el-option
          v-for="item in dictionaries.energy_type"
          :key="item"
          :label="item"
          :value="item"
        />
      </el-select>

      <el-switch v-model="query.expiring" active-text="仅看 30 天内到期" @change="handleSearch" />

      <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
    </div>

    <!-- 车辆列表 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div class="chart-card__title">
          车辆档案
          <span class="text-muted" style="font-size: 12px; font-weight: 400">
            共 {{ total }} 台
          </span>
        </div>
        <span class="text-muted" style="font-size: 12px">
          保险、营运证或保养日期任一已过期/30 天内到期，会在对应列标红或标橙提示
        </span>
      </div>

      <el-table :data="list" row-key="id" border stripe style="width: 100%">
        <el-table-column prop="plate_number" label="车牌号" width="120" fixed="left">
          <template #default="{ row }">
            <span class="mono">{{ row.plate_number }}</span>
          </template>
        </el-table-column>

        <el-table-column
          prop="brand_model"
          label="品牌型号"
          min-width="150"
          show-overflow-tooltip
        />

        <el-table-column prop="vehicle_type" label="类型" width="120">
          <template #default="{ row }">
            <span class="text-muted">{{ row.vehicle_type || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="energy_type" label="能源" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.energy_type" size="small" effect="plain" :type="energyTagType(row.energy_type)">
              {{ row.energy_type }}
            </el-tag>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>

        <el-table-column prop="home_region_name" label="常驻区域" width="120">
          <template #default="{ row }">
            <span>{{ row.home_region_name || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="绑定驾驶员" width="120">
          <template #default="{ row }">
            <span v-if="row.bound_driver_name">{{ row.bound_driver_name }}</span>
            <span v-else class="text-muted">未绑定</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusInfo(row.status).type" size="small" effect="light">
              {{ statusInfo(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="mileage_total" label="累计里程(km)" width="130" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.mileage_total, 0) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="order_count" label="订单数" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.order_count, 0) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="total_income" label="累计收入(元)" width="130" align="right">
          <template #default="{ row }">
            <span class="mono">{{ money(row.total_income) }}</span>
          </template>
        </el-table-column>

        <el-table-column
          v-for="col in expiryColumns"
          :key="col.prop"
          :label="col.label"
          :width="col.width"
        >
          <template #default="{ row }">
            <span :class="expireInfo(row[col.prop]).cls">{{ expireInfo(row[col.prop]).text }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openBind(row)">
              {{ row.bound_driver_name ? '换绑驾驶员' : '绑定驾驶员' }}
            </el-button>
            <el-dropdown trigger="click" @command="(cmd) => changeStatus(row, cmd)">
              <el-button link type="primary">
                变更状态
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="1" :disabled="row.status === 1">在营</el-dropdown-item>
                  <el-dropdown-item :command="0" :disabled="row.status === 0">停运</el-dropdown-item>
                  <el-dropdown-item :command="2" :disabled="row.status === 2">维修</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无车辆数据，可点击右上角「新增车辆」录入档案" :image-size="80" />
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

    <!-- 新增 / 编辑车辆 -->
    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑车辆' : '新增车辆'"
      width="760px"
      top="6vh"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="14">
          <el-col :xs="24" :md="12">
            <el-form-item label="车牌号" prop="plate_number">
              <el-input v-model="form.plate_number" placeholder="如 苏A12345" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="品牌型号" prop="brand_model">
              <el-input v-model="form.brand_model" placeholder="如 大众朗逸 2022 款" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="车辆类型" prop="vehicle_type">
              <el-select v-model="form.vehicle_type" style="width: 100%">
                <el-option
                  v-for="item in dictionaries.vehicle_type"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="能源类型" prop="energy_type">
              <el-select v-model="form.energy_type" style="width: 100%">
                <el-option
                  v-for="item in dictionaries.energy_type"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="车身颜色" prop="color">
              <el-input v-model="form.color" placeholder="如 白色" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="核载人数" prop="seats">
              <el-input-number v-model="form.seats" :min="1" :max="60" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="常驻区域" prop="home_region_id">
              <el-select
                v-model="form.home_region_id"
                placeholder="请选择常驻区域"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option v-for="item in regions" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="车辆状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="在营" :value="1" />
                <el-option label="停运" :value="0" />
                <el-option label="维修" :value="2" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="购置日期" prop="purchase_date">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="购置价格(万元)" prop="purchase_price">
              <el-input-number
                v-model="form.purchase_price"
                :min="0"
                :precision="2"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="累计里程(km)" prop="mileage_total">
              <el-input-number v-model="form.mileage_total" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="保养周期(天)" prop="maintenance_cycle_days">
              <el-input-number
                v-model="form.maintenance_cycle_days"
                :min="1"
                :max="730"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="保险到期日" prop="insurance_expire">
              <el-date-picker
                v-model="form.insurance_expire"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="营运证到期日" prop="cert_expire">
              <el-date-picker
                v-model="form.cert_expire"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="下次保养日期" prop="next_maintenance_date">
              <el-date-picker
                v-model="form.next_maintenance_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
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
                placeholder="车辆特殊说明，如改装情况、随车设备等"
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

    <!-- 绑定 / 换绑驾驶员 -->
    <el-dialog
      v-model="bindVisible"
      :title="`人车绑定 - ${bindVehicle.plate_number || ''}`"
      width="640px"
      destroy-on-close
    >
      <div class="chart-card__desc" style="margin-left: 0">
        同一车辆同一班次最多绑定 2 名驾驶员；换绑请先解绑原有记录，历史绑定会保留可查。
      </div>

      <el-table :data="bindings" v-loading="bindLoading" size="small" border style="width: 100%">
        <el-table-column prop="driver_name" label="当前驾驶员" width="110" />
        <el-table-column label="班次" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="light" :type="shiftTagType(row.shift)">{{ row.shift }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="绑定日期" width="120">
          <template #default="{ row }">{{ formatDate(row.assign_date) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link type="danger" @click="unbind(row)">解绑</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="当前没有生效中的绑定关系" :image-size="60" />
        </template>
      </el-table>

      <el-divider style="margin: 14px 0" />

      <el-form ref="bindFormRef" :model="bindForm" :rules="bindRules" label-width="90px">
        <el-form-item label="驾驶员" prop="driver_id">
          <el-select
            v-model="bindForm.driver_id"
            placeholder="请选择在职驾驶员"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="item in drivers"
              :key="item.id"
              :label="`${item.name}（${item.phone || '无电话'}）`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="班次" prop="shift">
          <el-select v-model="bindForm.shift" style="width: 100%">
            <el-option label="白班" value="白班" />
            <el-option label="夜班" value="夜班" />
            <el-option label="全天" value="全天" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定日期" prop="assign_date">
          <el-date-picker
            v-model="bindForm.assign_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择绑定日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="bindForm.remark" placeholder="如 车辆交接说明" maxlength="200" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindSaving" @click="submitBind">确定绑定</el-button>
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
import { assignmentApi, driverApi, regionApi, vehicleApi } from '../api';
import { formatDate, money, thousands, VEHICLE_STATUS } from '../utils/format';

const loading = ref(false);
const saving = ref(false);
const list = ref([]);
const total = ref(0);
const regions = ref([]);
const drivers = ref([]);
const dictionaries = ref({ vehicle_type: [], energy_type: [], status: [] });
const stats = ref({ total: 0, active: 0, idle: 0, repair: 0, expiring: 0 });

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: null,
  home_region_id: null,
  vehicle_type: null,
  energy_type: null,
  expiring: false,
});

/** 保险 / 营运证 / 保养三列共用同一套到期判断。 */
const expiryColumns = [
  { prop: 'insurance_expire', label: '保险到期', width: 150 },
  { prop: 'cert_expire', label: '营运证到期', width: 160 },
  { prop: 'next_maintenance_date', label: '下次保养', width: 150 },
];

const statCards = computed(() => [
  {
    label: '车辆总数',
    value: stats.value.total,
    unit: '台',
    icon: 'Van',
    tone: 'blue',
    sub: `常驻区域 ${regions.value.length} 个`,
  },
  {
    label: '在营车辆',
    value: stats.value.active,
    unit: '台',
    icon: 'CircleCheck',
    tone: 'green',
    sub: '可参与调度派单',
  },
  {
    label: '停运车辆',
    value: stats.value.idle,
    unit: '台',
    icon: 'VideoPause',
    tone: 'purple',
    sub: '暂停营运，保留档案',
  },
  {
    label: '维修车辆',
    value: stats.value.repair,
    unit: '台',
    icon: 'Tools',
    tone: 'orange',
    sub: '维修完成后请改回在营',
  },
  {
    label: '30 天内到期',
    value: stats.value.expiring,
    unit: '台',
    icon: 'AlarmClock',
    tone: 'red',
    sub: '保险 / 营运证 / 保养，含已过期',
  },
]);

/* ------------------------------------------------------------ 数据加载 */

function buildParams() {
  const params = { page: query.page, page_size: query.page_size };
  if (query.keyword && query.keyword.trim()) params.keyword = query.keyword.trim();
  if (query.status !== null && query.status !== undefined && query.status !== '') {
    params.status = query.status;
  }
  if (query.home_region_id !== null && query.home_region_id !== undefined && query.home_region_id !== '') {
    params.home_region_id = query.home_region_id;
  }
  if (query.vehicle_type) params.vehicle_type = query.vehicle_type;
  if (query.energy_type) params.energy_type = query.energy_type;
  if (query.expiring) params.expiring = 30;
  return params;
}

async function load() {
  loading.value = true;
  try {
    const data = await vehicleApi.page(buildParams());
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

/** 车辆总数无法由单条分页接口取到，改为按状态分别取 total（并行 5 次轻量请求）。 */
async function loadStats() {
  try {
    const [all, active, idle, repair, expiring] = await Promise.all([
      vehicleApi.page({ page: 1, page_size: 1 }),
      vehicleApi.page({ page: 1, page_size: 1, status: 1 }),
      vehicleApi.page({ page: 1, page_size: 1, status: 0 }),
      vehicleApi.page({ page: 1, page_size: 1, status: 2 }),
      vehicleApi.page({ page: 1, page_size: 1, expiring: 30 }),
    ]);
    stats.value = {
      total: all.total || 0,
      active: active.total || 0,
      idle: idle.total || 0,
      repair: repair.total || 0,
      expiring: expiring.total || 0,
    };
  } catch (error) {
    // 拦截器已统一提示
  }
}

/** 下拉选项（区域 / 在职驾驶员 / 字典）变化不频繁，进入页面时加载一次即可。 */
async function loadOptions() {
  try {
    const [regionList, driverList, dict] = await Promise.all([
      regionApi.all(),
      driverApi.all(),
      vehicleApi.dictionaries(),
    ]);
    regions.value = regionList || [];
    drivers.value = driverList || [];
    dictionaries.value = {
      vehicle_type: dict?.vehicle_type || [],
      energy_type: dict?.energy_type || [],
      status: dict?.status || [],
    };
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
  query.status = null;
  query.home_region_id = null;
  query.vehicle_type = null;
  query.energy_type = null;
  query.expiring = false;
  load();
}

/* ------------------------------------------------------------ 展示辅助 */

function statusInfo(status) {
  return VEHICLE_STATUS[status] || { text: '未知', type: 'info' };
}

function energyTagType(energy) {
  return { 燃油: 'info', 纯电: 'success', 混动: 'warning', 天然气: 'primary' }[energy] || 'info';
}

function shiftTagType(shift) {
  return { 白班: 'primary', 夜班: 'info', 全天: 'success' }[shift] || 'info';
}

/** 统一把后端日期字符串转成本地零点 Date，避免时区偏移导致差一天。 */
function parseDate(value) {
  if (!value) return null;
  const text = String(value).slice(0, 10);
  const date = new Date(`${text}T00:00:00`);
  if (!Number.isNaN(date.getTime())) return date;
  const fallback = new Date(value);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}

/** 到期状态：已过期标红、30 天内标橙。 */
function expireInfo(value) {
  const date = parseDate(value);
  if (!date) return { text: '—', cls: 'text-muted' };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((date.getTime() - today.getTime()) / 86400000);
  const text = formatDate(date);
  if (days < 0) return { text: `${text} 已过期`, cls: 'text-danger' };
  if (days <= 30) return { text: `${text} 即将到期`, cls: 'text-warning' };
  return { text, cls: '' };
}

/* ------------------------------------------------------------ 新增 / 编辑 */

const dialogVisible = ref(false);
const formRef = ref(null);

function emptyForm() {
  return {
    id: null,
    plate_number: '',
    brand_model: '',
    color: '',
    vehicle_type: '巡游出租车',
    energy_type: '燃油',
    seats: 5,
    purchase_date: '',
    purchase_price: null,
    mileage_total: 0,
    insurance_expire: '',
    cert_expire: '',
    next_maintenance_date: '',
    maintenance_cycle_days: 90,
    home_region_id: null,
    status: 1,
    remark: '',
  };
}

const form = reactive(emptyForm());

const rules = {
  plate_number: [
    { required: true, message: '请输入车牌号', trigger: 'blur' },
    { max: 20, message: '车牌号不超过 20 个字符', trigger: 'blur' },
  ],
  brand_model: [
    { required: true, message: '请输入品牌型号', trigger: 'blur' },
    { max: 50, message: '品牌型号不超过 50 个字符', trigger: 'blur' },
  ],
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
    plate_number: form.plate_number,
    brand_model: form.brand_model,
    color: form.color || null,
    vehicle_type: form.vehicle_type,
    energy_type: form.energy_type,
    seats: form.seats ?? 5,
    purchase_date: form.purchase_date || null,
    purchase_price: form.purchase_price ?? null,
    mileage_total: form.mileage_total ?? 0,
    insurance_expire: form.insurance_expire || null,
    cert_expire: form.cert_expire || null,
    next_maintenance_date: form.next_maintenance_date || null,
    maintenance_cycle_days: form.maintenance_cycle_days ?? 90,
    home_region_id: form.home_region_id || null,
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
      await vehicleApi.update(form.id, buildPayload());
    } else {
      await vehicleApi.create(buildPayload());
    }
    ElMessage.success(editing ? '车辆信息已保存' : '车辆已新增');
    dialogVisible.value = false;
    await loadAll();
  } catch (error) {
    // 拦截器已统一提示（如车牌号重复）
  } finally {
    saving.value = false;
  }
}

/* ------------------------------------------------------------ 状态 / 删除 */

async function changeStatus(row, status) {
  if (row.status === status) return;
  try {
    await vehicleApi.updateStatus(row.id, status);
    ElMessage.success(`「${row.plate_number}」状态已改为${statusInfo(status).text}`);
    await loadAll();
  } catch (error) {
    // 拦截器已统一提示
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除车辆「${row.plate_number}」吗？删除后档案不可恢复；已产生营运记录的车辆请改为停运。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    );
  } catch (error) {
    return; // 用户取消
  }
  try {
    await vehicleApi.remove(row.id);
    ElMessage.success('车辆已删除');
    await loadAll();
  } catch (error) {
    // 拦截器已统一提示（存在营运记录时后端返回 400）
  }
}

/* ------------------------------------------------------------ 人车绑定 */

const bindVisible = ref(false);
const bindLoading = ref(false);
const bindSaving = ref(false);
const bindFormRef = ref(null);
const bindVehicle = ref({});
const bindings = ref([]);
const bindForm = reactive({
  vehicle_id: null,
  driver_id: null,
  shift: '白班',
  assign_date: formatDate(new Date()),
  remark: '',
});

const bindRules = {
  driver_id: [{ required: true, message: '请选择驾驶员', trigger: 'change' }],
  shift: [{ required: true, message: '请选择班次', trigger: 'change' }],
  assign_date: [{ required: true, message: '请选择绑定日期', trigger: 'change' }],
};

async function loadBindings(vehicleId) {
  bindLoading.value = true;
  try {
    const data = await assignmentApi.page({ vehicle_id: vehicleId, status: 1, page: 1, page_size: 20 });
    bindings.value = data.items || [];
  } catch (error) {
    bindings.value = [];
  } finally {
    bindLoading.value = false;
  }
}

function openBind(row) {
  bindVehicle.value = row;
  bindForm.vehicle_id = row.id;
  bindForm.driver_id = row.bound_driver_id || null;
  bindForm.shift = '白班';
  bindForm.assign_date = formatDate(new Date());
  bindForm.remark = '';
  bindVisible.value = true;
  loadBindings(row.id);
}

async function submitBind() {
  if (!bindFormRef.value) return;
  try {
    await bindFormRef.value.validate();
  } catch (error) {
    return; // 表单校验未通过
  }
  bindSaving.value = true;
  try {
    await assignmentApi.create({
      vehicle_id: bindForm.vehicle_id,
      driver_id: bindForm.driver_id,
      shift: bindForm.shift,
      assign_date: bindForm.assign_date,
      remark: bindForm.remark || null,
    });
    ElMessage.success('绑定成功');
    await Promise.all([loadBindings(bindForm.vehicle_id), loadAll()]);
  } catch (error) {
    // 拦截器已统一提示（同一班次超过 2 人或重复绑定返回 400）
  } finally {
    bindSaving.value = false;
  }
}

async function unbind(row) {
  try {
    await ElMessageBox.confirm(
      `确认解绑「${row.driver_name}」与「${bindVehicle.value.plate_number}」的绑定关系吗？`,
      '解绑确认',
      { type: 'warning', confirmButtonText: '确认解绑', cancelButtonText: '取消' }
    );
  } catch (error) {
    return; // 用户取消
  }
  try {
    await assignmentApi.remove(row.id);
    ElMessage.success('已解绑');
    await Promise.all([loadBindings(bindForm.vehicle_id), loadAll()]);
  } catch (error) {
    // 拦截器已统一提示
  }
}

onMounted(async () => {
  await loadOptions();
  await loadAll();
});
</script>

<style scoped>
:deep(.el-table .cell) {
  word-break: break-word;
}
</style>
