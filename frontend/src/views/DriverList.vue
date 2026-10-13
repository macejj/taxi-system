<template>
  <div v-loading="loading">
    <PageHeader
      title="驾驶员管理"
      description="维护驾驶员档案（从业资格、联系方式、常驻区域与服务表现），并跟踪驾驶证有效期，保障人车绑定与排班有据可依。"
    >
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增驾驶员</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 人员统计 -->
    <el-row :gutter="14" class="mb-16">
      <el-col v-for="card in statCards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="姓名 / 身份证号 / 电话"
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="query.status"
        placeholder="在职状态"
        clearable
        style="width: 130px"
        @change="handleSearch"
      >
        <el-option label="在职" :value="1" />
        <el-option label="离职" :value="0" />
        <el-option label="休假" :value="2" />
      </el-select>

      <el-select
        v-model="query.home_region_id"
        placeholder="常驻区域"
        clearable
        filterable
        style="width: 170px"
        @change="handleSearch"
      >
        <el-option v-for="item in regions" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>

      <el-switch
        v-model="query.expiring"
        active-text="仅看 30 天内驾驶证到期"
        @change="handleSearch"
      />

      <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
    </div>

    <!-- 驾驶员列表 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div class="chart-card__title">
          驾驶员档案
          <span class="text-muted" style="font-size: 12px; font-weight: 400">
            共 {{ total }} 人
          </span>
        </div>
        <span class="text-muted" style="font-size: 12px">
          身份证号按脱敏规则展示（前 6 位 + ******** + 后 4 位），仅用于档案核对
        </span>
      </div>

      <el-table :data="list" row-key="id" border stripe style="width: 100%">
        <el-table-column prop="name" label="姓名" width="100" fixed="left">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="gender" label="性别" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="genderInfo(row.gender).type" size="small" effect="light">
              {{ genderInfo(row.gender).text }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="身份证号" width="190">
          <template #default="{ row }">
            <span class="mono">{{ maskIdCard(row.id_card) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="license_no" label="驾驶证号" width="140">
          <template #default="{ row }">
            <span class="mono">{{ row.license_no || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="qualification_no" label="从业资格证号" width="150">
          <template #default="{ row }">
            <span class="mono">{{ row.qualification_no || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="phone" label="联系电话" width="130">
          <template #default="{ row }">
            <span class="mono">{{ row.phone || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="home_region_name" label="常驻区域" width="120">
          <template #default="{ row }">
            <span>{{ row.home_region_name || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="绑定车辆" width="120">
          <template #default="{ row }">
            <span v-if="row.bound_plate" class="mono">{{ row.bound_plate }}</span>
            <span v-else class="text-muted">未绑定</span>
          </template>
        </el-table-column>

        <el-table-column label="服务评分" width="190">
          <template #default="{ row }">
            <div class="rate-cell">
              <el-rate
                :model-value="Number(row.rating) || 0"
                disabled
                allow-half
                size="small"
              />
              <span class="mono text-muted">{{ thousands(row.rating, 2) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="complaint_count" label="投诉次数" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="row.complaint_count ? 'text-danger' : ''">
              {{ thousands(row.complaint_count, 0) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="violation_count" label="违章次数" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="row.violation_count ? 'text-warning' : ''">
              {{ thousands(row.violation_count, 0) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusInfo(row.status).type" size="small" effect="light">
              {{ statusInfo(row.status).text }}
            </el-tag>
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

        <el-table-column label="驾驶证有效期" width="170">
          <template #default="{ row }">
            <span :class="expireInfo(row.license_expire).cls">
              {{ expireInfo(row.license_expire).text }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无驾驶员数据，可点击右上角「新增驾驶员」录入档案" :image-size="80" />
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

    <!-- 新增 / 编辑驾驶员 -->
    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑驾驶员' : '新增驾驶员'"
      width="760px"
      top="6vh"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="14">
          <el-col :xs="24" :md="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="性别" prop="gender">
              <el-radio-group v-model="form.gender">
                <el-radio value="M">男</el-radio>
                <el-radio value="F">女</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="身份证号" prop="id_card">
              <el-input v-model="form.id_card" maxlength="18" placeholder="18 位身份证号" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="form.phone" maxlength="11" placeholder="11 位手机号" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="驾驶证号" prop="license_no">
              <el-input v-model="form.license_no" placeholder="请输入驾驶证号" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="从业资格证号" prop="qualification_no">
              <el-input v-model="form.qualification_no" placeholder="请输入从业资格证号" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="出生日期" prop="birth_date">
              <el-date-picker
                v-model="form.birth_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="入职日期" prop="hire_date">
              <el-date-picker
                v-model="form.hire_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="驾驶证有效期" prop="license_expire">
              <el-date-picker
                v-model="form.license_expire"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
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
            <el-form-item label="服务评分" prop="rating">
              <el-rate v-model="form.rating" allow-half show-score score-template="{value} 分" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="在职状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="在职" :value="1" />
                <el-option label="离职" :value="0" />
                <el-option label="休假" :value="2" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="投诉次数" prop="complaint_count">
              <el-input-number v-model="form.complaint_count" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="违章次数" prop="violation_count">
              <el-input-number v-model="form.violation_count" :min="0" :max="999" style="width: 100%" />
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
                placeholder="如 服务表彰、培训情况等"
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
import { driverApi, regionApi } from '../api';
import { DRIVER_STATUS, formatDate, money, thousands } from '../utils/format';

const loading = ref(false);
const saving = ref(false);
const list = ref([]);
const total = ref(0);
const regions = ref([]);
const stats = ref({ total: 0, active: 0, leave: 0, rest: 0, expiring: 0 });

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: null,
  home_region_id: null,
  expiring: false,
});

const statCards = computed(() => [
  {
    label: '驾驶员总数',
    value: stats.value.total,
    unit: '人',
    icon: 'User',
    tone: 'blue',
    sub: `常驻区域 ${regions.value.length} 个`,
  },
  {
    label: '在职驾驶员',
    value: stats.value.active,
    unit: '人',
    icon: 'CircleCheck',
    tone: 'green',
    sub: '可参与人车绑定与排班',
  },
  {
    label: '离职驾驶员',
    value: stats.value.leave,
    unit: '人',
    icon: 'UserFilled',
    tone: 'purple',
    sub: '档案保留，不可派单',
  },
  {
    label: '休假驾驶员',
    value: stats.value.rest,
    unit: '人',
    icon: 'Coffee',
    tone: 'orange',
    sub: '临时停止排班',
  },
  {
    label: '30 天内驾驶证到期',
    value: stats.value.expiring,
    unit: '人',
    icon: 'AlarmClock',
    tone: 'red',
    sub: '含已过期，需尽快换证',
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
  if (query.expiring) params.expiring = 30;
  return params;
}

async function load() {
  loading.value = true;
  try {
    const data = await driverApi.page(buildParams());
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

/** 驾驶员总数按状态分别取 total（并行 5 次轻量请求），避免整表拉取。 */
async function loadStats() {
  try {
    const [all, active, leave, rest, expiring] = await Promise.all([
      driverApi.page({ page: 1, page_size: 1 }),
      driverApi.page({ page: 1, page_size: 1, status: 1 }),
      driverApi.page({ page: 1, page_size: 1, status: 0 }),
      driverApi.page({ page: 1, page_size: 1, status: 2 }),
      driverApi.page({ page: 1, page_size: 1, expiring: 30 }),
    ]);
    stats.value = {
      total: all.total || 0,
      active: active.total || 0,
      leave: leave.total || 0,
      rest: rest.total || 0,
      expiring: expiring.total || 0,
    };
  } catch (error) {
    // 拦截器已统一提示
  }
}

async function loadRegions() {
  try {
    regions.value = (await regionApi.all()) || [];
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
  query.expiring = false;
  load();
}

/* ------------------------------------------------------------ 展示辅助 */

function statusInfo(status) {
  return DRIVER_STATUS[status] || { text: '未知', type: 'info' };
}

function genderInfo(gender) {
  return gender === 'F' ? { text: '女', type: 'warning' } : { text: '男', type: 'primary' };
}

/** 身份证号脱敏：前 6 位 + ******** + 后 4 位。 */
function maskIdCard(value) {
  const text = String(value || '');
  if (!text) return '—';
  if (text.length <= 10) return text;
  return `${text.slice(0, 6)}********${text.slice(-4)}`;
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

/** 驾驶证到期状态：已过期标红、30 天内标橙。 */
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
    name: '',
    gender: 'M',
    id_card: '',
    license_no: '',
    qualification_no: '',
    phone: '',
    birth_date: '',
    hire_date: '',
    license_expire: '',
    rating: 5,
    complaint_count: 0,
    violation_count: 0,
    home_region_id: null,
    status: 1,
    remark: '',
  };
}

const form = reactive(emptyForm());

/** 身份证号：18 位，末位可为 X。 */
function validateIdCard(rule, value, callback) {
  if (!value) {
    callback(new Error('请输入身份证号'));
    return;
  }
  if (!/^\d{17}[\dXx]$/.test(value)) {
    callback(new Error('身份证号应为 18 位（前 17 位数字，末位数字或 X）'));
    return;
  }
  callback();
}

/** 手机号非必填，填写时校验格式。 */
function validatePhone(rule, value, callback) {
  if (!value) {
    callback();
    return;
  }
  if (!/^1[3-9]\d{9}$/.test(value)) {
    callback(new Error('请输入正确的 11 位手机号'));
    return;
  }
  callback();
}

const rules = {
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { max: 30, message: '姓名不超过 30 个字符', trigger: 'blur' },
  ],
  id_card: [{ required: true, validator: validateIdCard, trigger: 'blur' }],
  license_no: [{ required: true, message: '请输入驾驶证号', trigger: 'blur' }],
  phone: [{ validator: validatePhone, trigger: 'blur' }],
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
    name: form.name,
    gender: form.gender || 'M',
    id_card: form.id_card,
    license_no: form.license_no,
    qualification_no: form.qualification_no || null,
    phone: form.phone || null,
    birth_date: form.birth_date || null,
    hire_date: form.hire_date || null,
    license_expire: form.license_expire || null,
    rating: form.rating ?? 5,
    complaint_count: form.complaint_count ?? 0,
    violation_count: form.violation_count ?? 0,
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
      await driverApi.update(form.id, buildPayload());
    } else {
      await driverApi.create(buildPayload());
    }
    ElMessage.success(editing ? '驾驶员信息已保存' : '驾驶员已新增');
    dialogVisible.value = false;
    await loadAll();
  } catch (error) {
    // 拦截器已统一提示（如身份证号重复）
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除驾驶员「${row.name}」吗？删除后档案不可恢复；已产生营运记录的驾驶员请改为离职。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    );
  } catch (error) {
    return; // 用户取消
  }
  try {
    await driverApi.remove(row.id);
    ElMessage.success('驾驶员已删除');
    await loadAll();
  } catch (error) {
    // 拦截器已统一提示（存在营运记录时后端返回 400）
  }
}

onMounted(async () => {
  await loadRegions();
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
