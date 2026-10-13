<template>
  <div v-loading="loading">
    <PageHeader
      title="人车绑定排班"
      description="维护车辆与驾驶员的绑定关系及班次安排，是营运订单归属与调度派单的基础；解绑仅结束当前关系，历史记录完整保留。"
    >
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增绑定</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-select
        v-model="query.vehicle_id"
        placeholder="选择车辆"
        clearable
        filterable
        style="width: 190px"
        @change="handleSearch"
      >
        <el-option
          v-for="item in vehicles"
          :key="item.id"
          :label="`${item.plate_number}（${item.brand_model}）`"
          :value="item.id"
        />
      </el-select>

      <el-select
        v-model="query.driver_id"
        placeholder="选择驾驶员"
        clearable
        filterable
        style="width: 170px"
        @change="handleSearch"
      >
        <el-option
          v-for="item in drivers"
          :key="item.id"
          :label="`${item.name}（${item.phone || '无电话'}）`"
          :value="item.id"
        />
      </el-select>

      <el-select
        v-model="query.status"
        placeholder="绑定状态"
        clearable
        style="width: 140px"
        @change="handleSearch"
      >
        <el-option label="生效中" :value="1" />
        <el-option label="已解绑" :value="0" />
      </el-select>

      <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
    </div>

    <!-- 绑定记录 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div class="chart-card__title">
          绑定记录
          <span class="text-muted" style="font-size: 12px; font-weight: 400">
            共 {{ total }} 条
          </span>
        </div>
        <span class="text-muted" style="font-size: 12px">
          同一车辆同一班次最多绑定 2 名驾驶员；一个驾驶员同时只应有一条生效绑定
        </span>
      </div>

      <el-table :data="list" row-key="id" border stripe style="width: 100%">
        <el-table-column prop="plate_number" label="车辆车牌" width="130" fixed="left">
          <template #default="{ row }">
            <span class="mono">{{ row.plate_number || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="driver_name" label="驾驶员" width="110">
          <template #default="{ row }">
            <span>{{ row.driver_name || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="driver_phone" label="联系电话" width="140">
          <template #default="{ row }">
            <span class="mono">{{ row.driver_phone || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="shift" label="班次" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="shiftTagType(row.shift)" size="small" effect="light">
              {{ row.shift || '—' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="绑定日期" width="130">
          <template #default="{ row }">
            <span class="mono">{{ formatDate(row.assign_date) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="解绑日期" width="130">
          <template #default="{ row }">
            <span v-if="row.unassign_date" class="mono">{{ formatDate(row.unassign_date) }}</span>
            <span v-else class="text-muted">—</span>
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

        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              :disabled="row.status !== 1"
              @click="handleUnbind(row)"
            >
              解绑
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无绑定记录，可点击右上角「新增绑定」建立人车关系" :image-size="80" />
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

    <!-- 新增绑定 -->
    <el-dialog v-model="dialogVisible" title="新增绑定" width="600px" destroy-on-close>
      <div class="chart-card__desc" style="margin-left: 0">
        绑定关系决定营运订单与调度指令的归属，请确认车辆与驾驶员的班次安排一致。
      </div>

      <el-alert
        v-if="existingBindings.length"
        type="info"
        :closable="false"
        show-icon
        class="mb-16"
        :title="`该车辆当前生效绑定：${existingText}`"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="车辆" prop="vehicle_id">
          <el-select
            v-model="form.vehicle_id"
            placeholder="请选择在营车辆"
            filterable
            style="width: 100%"
            @change="loadExisting"
          >
            <el-option
              v-for="item in vehicles"
              :key="item.id"
              :label="`${item.plate_number}（${item.brand_model}）`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="驾驶员" prop="driver_id">
          <el-select
            v-model="form.driver_id"
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
          <el-select v-model="form.shift" style="width: 100%">
            <el-option label="白班" value="白班" />
            <el-option label="夜班" value="夜班" />
            <el-option label="全天" value="全天" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定日期" prop="assign_date">
          <el-date-picker
            v-model="form.assign_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择绑定日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="如 车辆交接说明、代班原因等"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">确定绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import { assignmentApi, driverApi, vehicleApi } from '../api';
import { formatDate } from '../utils/format';

/** 绑定状态字典（format.js 未提供，本页局部定义）。 */
const ASSIGNMENT_STATUS = {
  0: { text: '已解绑', type: 'info' },
  1: { text: '生效中', type: 'success' },
};

const loading = ref(false);
const saving = ref(false);
const list = ref([]);
const total = ref(0);
const vehicles = ref([]);
const drivers = ref([]);

const query = reactive({
  page: 1,
  page_size: 20,
  vehicle_id: null,
  driver_id: null,
  status: null,
});

/* ------------------------------------------------------------ 数据加载 */

function buildParams() {
  const params = { page: query.page, page_size: query.page_size };
  if (query.vehicle_id !== null && query.vehicle_id !== undefined && query.vehicle_id !== '') {
    params.vehicle_id = query.vehicle_id;
  }
  if (query.driver_id !== null && query.driver_id !== undefined && query.driver_id !== '') {
    params.driver_id = query.driver_id;
  }
  if (query.status !== null && query.status !== undefined && query.status !== '') {
    params.status = query.status;
  }
  return params;
}

async function load() {
  loading.value = true;
  try {
    const data = await assignmentApi.page(buildParams());
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

/** 车辆与驾驶员下拉选项（车辆仅返回在营车辆，驾驶员仅返回在职人员）。 */
async function loadOptions() {
  try {
    const [vehicleList, driverList] = await Promise.all([vehicleApi.all(), driverApi.all()]);
    vehicles.value = vehicleList || [];
    drivers.value = driverList || [];
  } catch (error) {
    // 拦截器已统一提示
  }
}

async function loadAll() {
  await load();
}

function handleSearch() {
  query.page = 1;
  load();
}

function resetQuery() {
  query.page = 1;
  query.vehicle_id = null;
  query.driver_id = null;
  query.status = null;
  load();
}

/* ------------------------------------------------------------ 展示辅助 */

function statusInfo(status) {
  return ASSIGNMENT_STATUS[status] || { text: '未知', type: 'info' };
}

function shiftTagType(shift) {
  return { 白班: 'primary', 夜班: 'info', 全天: 'success' }[shift] || 'info';
}

/* ------------------------------------------------------------ 新增绑定 */

const dialogVisible = ref(false);
const formRef = ref(null);
const existingBindings = ref([]);

const existingText = computed(() =>
  existingBindings.value
    .map((item) => `${item.driver_name || '未知'}（${item.shift || '未填班次'}）`)
    .join('、')
);

function emptyForm() {
  return {
    vehicle_id: null,
    driver_id: null,
    shift: '白班',
    assign_date: formatDate(new Date()),
    remark: '',
  };
}

const form = reactive(emptyForm());

const rules = {
  vehicle_id: [{ required: true, message: '请选择车辆', trigger: 'change' }],
  driver_id: [{ required: true, message: '请选择驾驶员', trigger: 'change' }],
  shift: [{ required: true, message: '请选择班次', trigger: 'change' }],
  assign_date: [{ required: true, message: '请选择绑定日期', trigger: 'change' }],
};

function openCreate() {
  Object.assign(form, emptyForm());
  existingBindings.value = [];
  dialogVisible.value = true;
}

/** 选择车辆后提示该车已有的生效绑定，避免超出「同班次最多 2 人」的限制。 */
async function loadExisting() {
  if (!form.vehicle_id) {
    existingBindings.value = [];
    return;
  }
  try {
    const data = await assignmentApi.page({
      vehicle_id: form.vehicle_id,
      status: 1,
      page: 1,
      page_size: 20,
    });
    existingBindings.value = data.items || [];
  } catch (error) {
    existingBindings.value = [];
  }
}

async function submitForm() {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
  } catch (error) {
    return; // 表单校验未通过，交由 el-form 提示
  }
  saving.value = true;
  try {
    await assignmentApi.create({
      vehicle_id: form.vehicle_id,
      driver_id: form.driver_id,
      shift: form.shift,
      assign_date: form.assign_date,
      remark: form.remark || null,
    });
    ElMessage.success('绑定成功');
    dialogVisible.value = false;
    await load();
  } catch (error) {
    // 拦截器已统一提示（重复绑定或同班次超过 2 人返回 400）
  } finally {
    saving.value = false;
  }
}

/* ------------------------------------------------------------ 解绑 */

async function handleUnbind(row) {
  try {
    await ElMessageBox.confirm(
      `确认解绑「${row.driver_name || '该驾驶员'}」与「${row.plate_number || '该车辆'}」的绑定关系吗？解绑后保留历史记录，仅结束当前绑定关系。`,
      '解绑确认',
      { type: 'warning', confirmButtonText: '确认解绑', cancelButtonText: '取消' }
    );
  } catch (error) {
    return; // 用户取消
  }
  try {
    await assignmentApi.remove(row.id);
    ElMessage.success('已解绑，历史记录已保留');
    await load();
  } catch (error) {
    // 拦截器已统一提示
  }
}

onMounted(async () => {
  await loadOptions();
  await load();
});
</script>

<style scoped>
:deep(.el-table .cell) {
  word-break: break-word;
}
</style>
