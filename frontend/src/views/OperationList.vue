<template>
  <div v-loading="loading">
    <PageHeader
      title="营运订单管理"
      description="本页管理已完成的城市出租车营运订单（供给侧数据），支持按日期、车辆、驾驶员、区域、支付方式等多维筛选，并提供 Excel 批量导入、模板下载与筛选结果导出。"
    >
      <template #extra>
        <el-tag type="info" effect="plain">
          <el-icon><Tickets /></el-icon>
          共 {{ thousands(total) }} 条订单
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选条 -->
    <div class="filter-bar">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="日期区间">
          <el-date-picker
            v-model="query.start_range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            :clearable="false"
            style="width: 250px"
          />
        </el-form-item>
        <el-form-item label="车牌">
          <el-select
            v-model="query.vehicle_id"
            placeholder="全部车辆"
            clearable
            filterable
            style="width: 150px"
          >
            <el-option
              v-for="item in vehicles"
              :key="item.id"
              :label="item.plate_number"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="驾驶员">
          <el-select
            v-model="query.driver_id"
            placeholder="全部驾驶员"
            clearable
            filterable
            style="width: 150px"
          >
            <el-option
              v-for="item in drivers"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="上车区域">
          <el-select
            v-model="query.region_id"
            placeholder="全部区域"
            clearable
            filterable
            style="width: 160px"
          >
            <el-option
              v-for="item in regions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select
            v-model="query.pay_type"
            placeholder="全部方式"
            clearable
            style="width: 130px"
          >
            <el-option v-for="item in payTypes" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="时段">
          <el-select v-model="query.peak" placeholder="全部时段" clearable style="width: 110px">
            <el-option label="仅高峰" :value="1" />
            <el-option label="仅平峰" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额区间">
          <el-input-number
            v-model="query.min_amount"
            :min="0"
            :max="99999"
            :controls="false"
            placeholder="最低"
            style="width: 88px"
          />
          <span class="text-muted" style="margin: 0 6px">-</span>
          <el-input-number
            v-model="query.max_amount"
            :min="0"
            :max="99999"
            :controls="false"
            placeholder="最高"
            style="width: 88px"
          />
        </el-form-item>
        <el-form-item label="订单号">
          <el-input
            v-model="query.keyword"
            placeholder="订单号关键字"
            clearable
            style="width: 170px"
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="search">查询</el-button>
          <el-button :icon="RefreshLeft" @click="reset">重置</el-button>
          <el-radio-group v-model="quickDays" size="small" style="margin-left: 6px" @change="applyQuick">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
            <el-radio-button :value="90">近 90 天</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </div>

    <!-- 汇总条 -->
    <el-row :gutter="14">
      <el-col v-for="card in summaryCards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4">
        <StatCard v-bind="card" class="mb-16" />
      </el-col>
    </el-row>

    <!-- 表格 -->
    <div class="table-card">
      <div class="table-toolbar">
        <div>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增订单</el-button>
          <el-button :icon="Upload" @click="triggerImport">导入 Excel</el-button>
          <el-button :icon="Download" @click="downloadTemplate">下载模板</el-button>
        </div>
        <div>
          <span class="text-muted" style="font-size: 12px; margin-right: 8px">
            导出当前筛选结果
          </span>
          <el-button :icon="Document" @click="exportData('csv')">导出 CSV</el-button>
          <el-button :icon="Grid" @click="exportData('xlsx')">导出 Excel</el-button>
        </div>
      </div>

      <el-upload
        ref="uploadRef"
        :show-file-list="false"
        accept=".xlsx,.xls"
        :http-request="handleImport"
      />

      <el-table :data="rows" border stripe height="520" style="width: 100%">
        <el-table-column prop="order_no" label="订单号" width="190" fixed="left">
          <template #default="{ row }">
            <span class="mono">{{ row.order_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="plate_number" label="车牌号" width="120" />
        <el-table-column prop="driver_name" label="驾驶员" width="90" />
        <el-table-column label="上车区域 → 下车区域" width="210">
          <template #default="{ row }">
            <span>{{ row.pickup_region_name || '-' }}</span>
            <el-icon class="text-muted" style="margin: 0 4px"><Right /></el-icon>
            <span>{{ row.dropoff_region_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上车时间" width="150">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.start_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="下车时间" width="150">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.end_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时长(分钟)" width="105" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.duration_minutes, 1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="载客里程" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.loaded_mileage, 1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="空驶里程" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ thousands(row.empty_mileage, 1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100" align="right">
          <template #default="{ row }">
            <span class="mono text-success">{{ money(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="pay_type" label="支付方式" width="100" />
        <el-table-column prop="weather" label="天气" width="80" />
        <el-table-column label="高峰" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_peak" type="warning" size="small" effect="light">高峰</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">平峰</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="当前筛选条件下暂无营运订单" :image-size="80" />
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
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="营运订单详情" size="520px">
      <el-descriptions v-if="current" :column="1" size="small" border>
        <el-descriptions-item label="订单号">
          <span class="mono">{{ current.order_no }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="车牌号">{{ current.plate_number || '-' }}</el-descriptions-item>
        <el-descriptions-item label="驾驶员">{{ current.driver_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="上车区域">
          {{ current.pickup_region_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="下车区域">
          {{ current.dropoff_region_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="上车时间">
          {{ formatDateTime(current.start_time, true) }}
        </el-descriptions-item>
        <el-descriptions-item label="下车时间">
          {{ formatDateTime(current.end_time, true) }}
        </el-descriptions-item>
        <el-descriptions-item label="时长(分钟)">
          {{ thousands(current.duration_minutes, 1) }}
        </el-descriptions-item>
        <el-descriptions-item label="载客里程(公里)">
          {{ thousands(current.loaded_mileage, 2) }}
        </el-descriptions-item>
        <el-descriptions-item label="空驶里程(公里)">
          {{ thousands(current.empty_mileage, 2) }}
        </el-descriptions-item>
        <el-descriptions-item label="平均速度(公里/小时)">
          {{ thousands(current.avg_speed, 1) }}
        </el-descriptions-item>
        <el-descriptions-item label="金额(元)">
          <span class="text-success mono">{{ money(current.amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ current.pay_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="天气">{{ current.weather || '-' }}</el-descriptions-item>
        <el-descriptions-item label="乘客人数">{{ current.passenger_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="是否高峰">
          <el-tag v-if="current.is_peak" type="warning" size="small" effect="light">高峰</el-tag>
          <el-tag v-else type="info" size="small" effect="plain">平峰</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="统计日期">{{ formatDate(current.stat_date) }}</el-descriptions-item>
        <el-descriptions-item label="所属小时">
          {{ current.hour === null || current.hour === undefined ? '-' : hourLabel(current.hour) }}
        </el-descriptions-item>
        <el-descriptions-item label="星期">{{ weekdayText(current.weekday) }}</el-descriptions-item>
        <el-descriptions-item label="记录 ID">{{ current.id }}</el-descriptions-item>
      </el-descriptions>
      <div class="text-muted" style="font-size: 12px; margin-top: 12px; line-height: 1.7">
        时长、平均速度、高峰标记由后端依据上下车时间与载客里程自动派生，编辑时间或里程后会自动重算。
      </div>
    </el-drawer>

    <!-- 新增 / 编辑对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="form.id ? '编辑营运订单' : '新增营运订单'"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="112px">
        <el-row :gutter="14">
          <el-col :xs="24" :md="12">
            <el-form-item label="订单号" prop="order_no">
              <el-input v-model="form.order_no" placeholder="留空则由系统自动生成" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="车牌号" prop="vehicle_id">
              <el-select
                v-model="form.vehicle_id"
                placeholder="请选择车辆"
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in vehicles"
                  :key="item.id"
                  :label="item.plate_number"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="驾驶员" prop="driver_id">
              <el-select
                v-model="form.driver_id"
                placeholder="请选择驾驶员"
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in drivers"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="支付方式">
              <el-select v-model="form.pay_type" placeholder="请选择支付方式" style="width: 100%">
                <el-option v-for="item in payTypes" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="上车区域">
              <el-select
                v-model="form.pickup_region_id"
                placeholder="请选择上车区域"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in regions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="下车区域">
              <el-select
                v-model="form.dropoff_region_id"
                placeholder="请选择下车区域"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in regions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="上车时间" prop="start_time">
              <el-date-picker
                v-model="form.start_time"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="选择上车时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="下车时间" prop="end_time">
              <el-date-picker
                v-model="form.end_time"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="选择下车时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="载客里程" prop="loaded_mileage">
              <el-input-number
                v-model="form.loaded_mileage"
                :min="0"
                :max="9999"
                :precision="2"
                :step="0.5"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="空驶里程">
              <el-input-number
                v-model="form.empty_mileage"
                :min="0"
                :max="9999"
                :precision="2"
                :step="0.5"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="金额(元)" prop="amount">
              <el-input-number
                v-model="form.amount"
                :min="0"
                :max="99999"
                :precision="2"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="乘客人数">
              <el-input-number
                v-model="form.passenger_count"
                :min="1"
                :max="20"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="天气">
              <el-select v-model="form.weather" placeholder="请选择天气" style="width: 100%">
                <el-option v-for="item in WEATHERS" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="时长与平均速度由上下车时间自动计算；下车时间不得早于上车时间。"
        />
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importVisible" title="Excel 导入结果" width="620px">
      <el-row :gutter="12" class="mb-16">
        <el-col :span="8">
          <div class="import-stat">
            <div class="import-stat__value">{{ importResult.total_rows || 0 }}</div>
            <div class="import-stat__label">总行数</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="import-stat">
            <div class="import-stat__value text-success">{{ importResult.imported || 0 }}</div>
            <div class="import-stat__label">成功导入</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="import-stat">
            <div class="import-stat__value text-warning">{{ importResult.duplicated || 0 }}</div>
            <div class="import-stat__label">重复跳过</div>
          </div>
        </el-col>
      </el-row>

      <template v-if="errorRows.length">
        <div class="chart-card__head">
          <div class="chart-card__title">错误行号（共 {{ errorRows.length }} 行）</div>
        </div>
        <el-scrollbar height="150px" class="import-scroll">
          <el-tag
            v-for="line in errorRows"
            :key="line"
            type="danger"
            size="small"
            effect="light"
            style="margin: 0 6px 6px 0"
          >
            第 {{ line }} 行
          </el-tag>
        </el-scrollbar>

        <div class="chart-card__head mt-16">
          <div class="chart-card__title">错误说明</div>
        </div>
        <el-scrollbar height="170px" class="import-scroll">
          <div v-for="(msg, index) in errorMessages" :key="index" class="import-error">
            <el-icon class="text-danger"><WarningFilled /></el-icon>
            <span>{{ msg }}</span>
          </div>
        </el-scrollbar>
      </template>
      <el-alert
        v-else
        type="success"
        :closable="false"
        show-icon
        title="全部导入成功"
        description="所有有效数据行均已写入数据库，重复订单号已自动跳过。"
      />

      <template #footer>
        <el-button type="primary" @click="importVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Document,
  Download,
  Grid,
  Plus,
  Refresh,
  RefreshLeft,
  Right,
  Search,
  Tickets,
  Upload,
  WarningFilled,
} from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';
import { driverApi, operationApi, regionApi, vehicleApi } from '../api';
import {
  WEEKDAYS,
  downloadWithAuth,
  formatDate,
  formatDateTime,
  hourLabel,
  money,
  recentRange,
  thousands,
} from '../utils/format';

const WEATHERS = ['晴', '多云', '阴', '小雨', '中雨', '大雨', '雪', '雾霾'];

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const summary = ref({});
const vehicles = ref([]);
const drivers = ref([]);
const regions = ref([]);
const payTypes = ref([]);
const quickDays = ref(30);

const query = reactive({
  page: 1,
  page_size: 20,
  start_range: recentRange(30),
  vehicle_id: null,
  driver_id: null,
  region_id: null,
  pay_type: null,
  peak: null,
  min_amount: null,
  max_amount: null,
  keyword: '',
});

const filters = ref({});

const detailVisible = ref(false);
const current = ref(null);
const formVisible = ref(false);
const formRef = ref(null);
const uploadRef = ref(null);
const importVisible = ref(false);
const importResult = ref({});
const errorRows = ref([]);
const errorMessages = ref([]);

const form = reactive({
  id: null,
  order_no: '',
  vehicle_id: null,
  driver_id: null,
  pickup_region_id: null,
  dropoff_region_id: null,
  start_time: '',
  end_time: '',
  loaded_mileage: 0,
  empty_mileage: 0,
  amount: 0,
  passenger_count: 1,
  pay_type: '微信',
  weather: '晴',
});

const rules = {
  vehicle_id: [{ required: true, message: '请选择车牌号', trigger: 'change' }],
  driver_id: [{ required: true, message: '请选择驾驶员', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择上车时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择下车时间', trigger: 'change' }],
  loaded_mileage: [{ required: true, message: '请填写载客里程', trigger: 'blur' }],
  amount: [{ required: true, message: '请填写订单金额', trigger: 'blur' }],
};

/** 当前筛选条件（不包含分页），用于列表、汇总与导出 */
const buildParams = () => ({
  start_date: query.start_range?.[0] || undefined,
  end_date: query.start_range?.[1] || undefined,
  vehicle_id: query.vehicle_id || undefined,
  driver_id: query.driver_id || undefined,
  region_id: query.region_id || undefined,
  pay_type: query.pay_type || undefined,
  peak: query.peak === 0 || query.peak === 1 ? query.peak : undefined,
  min_amount: query.min_amount === null || query.min_amount === '' ? undefined : query.min_amount,
  max_amount: query.max_amount === null || query.max_amount === '' ? undefined : query.max_amount,
  keyword: query.keyword ? query.keyword.trim() : undefined,
});

const summaryCards = computed(() => {
  const data = summary.value || {};
  return [
    {
      label: '订单总数',
      value: data.order_count ?? 0,
      unit: '单',
      icon: 'Tickets',
      tone: 'blue',
      sub: `筛选区间 ${query.start_range?.[0] || '-'} 至 ${query.start_range?.[1] || '-'}`,
    },
    {
      label: '总收入',
      value: data.total_income ?? 0,
      unit: '元',
      icon: 'Money',
      tone: 'green',
      digits: 2,
      sub: `单均收入 ${money(data.avg_amount)} 元`,
    },
    {
      label: '载客里程',
      value: data.loaded_mileage ?? 0,
      unit: '公里',
      icon: 'Odometer',
      tone: 'cyan',
      digits: 1,
    },
    {
      label: '空驶里程',
      value: data.empty_mileage ?? 0,
      unit: '公里',
      icon: 'Van',
      tone: 'orange',
      digits: 1,
    },
    {
      label: '单均收入',
      value: data.avg_amount ?? 0,
      unit: '元',
      icon: 'Coin',
      tone: 'purple',
      digits: 2,
    },
    {
      label: '空驶率',
      value: data.empty_rate ?? 0,
      unit: '%',
      icon: 'DataLine',
      tone: 'red',
      digits: 2,
      inverse: true,
      sub: '空驶里程 / 总里程，越低越好',
    },
  ];
});

function weekdayText(value) {
  if (value === null || value === undefined) return '-';
  return WEEKDAYS[value] || '-';
}

function applyQuick(days) {
  query.start_range = recentRange(days || 30);
  search();
}

async function loadList() {
  const data = await operationApi.page({ page: query.page, page_size: query.page_size, ...filters.value });
  rows.value = data?.items || [];
  total.value = data?.total || 0;
}

async function loadSummary() {
  summary.value = (await operationApi.summary(filters.value)) || {};
}

async function loadOptions() {
  const [vehicleList, driverList, regionList, typeList] = await Promise.all([
    vehicleApi.all().catch(() => []),
    driverApi.all().catch(() => []),
    regionApi.all().catch(() => []),
    operationApi.payTypes().catch(() => []),
  ]);
  vehicles.value = vehicleList || [];
  drivers.value = driverList || [];
  regions.value = regionList || [];
  payTypes.value =
    Array.isArray(typeList) && typeList.length ? typeList : ['微信', '支付宝', '现金', '银行卡'];
}

async function loadAll() {
  loading.value = true;
  filters.value = buildParams();
  try {
    await Promise.all([loadList(), loadSummary()]);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}

function search() {
  query.page = 1;
  loadAll();
}

function reload() {
  loadAll();
}

function reset() {
  query.page = 1;
  query.page_size = 20;
  query.start_range = recentRange(30);
  query.vehicle_id = null;
  query.driver_id = null;
  query.region_id = null;
  query.pay_type = null;
  query.peak = null;
  query.min_amount = null;
  query.max_amount = null;
  query.keyword = '';
  quickDays.value = 30;
  loadAll();
}

/* ------------------------------------------------------------------ 详情 */
function openDetail(row) {
  current.value = row;
  detailVisible.value = true;
}

/* ------------------------------------------------------------------ 新增 / 编辑 */
function resetForm() {
  form.id = null;
  form.order_no = '';
  form.vehicle_id = null;
  form.driver_id = null;
  form.pickup_region_id = null;
  form.dropoff_region_id = null;
  form.start_time = '';
  form.end_time = '';
  form.loaded_mileage = 0;
  form.empty_mileage = 0;
  form.amount = 0;
  form.passenger_count = 1;
  form.pay_type = payTypes.value[0] || '微信';
  form.weather = '晴';
}

function openCreate() {
  resetForm();
  formVisible.value = true;
  formRef.value?.clearValidate();
}

function openEdit(row) {
  resetForm();
  form.id = row.id;
  form.order_no = row.order_no || '';
  form.vehicle_id = row.vehicle_id ?? null;
  form.driver_id = row.driver_id ?? null;
  form.pickup_region_id = row.pickup_region_id ?? null;
  form.dropoff_region_id = row.dropoff_region_id ?? null;
  form.start_time = row.start_time ? String(row.start_time).replace('T', ' ').slice(0, 19) : '';
  form.end_time = row.end_time ? String(row.end_time).replace('T', ' ').slice(0, 19) : '';
  form.loaded_mileage = Number(row.loaded_mileage) || 0;
  form.empty_mileage = Number(row.empty_mileage) || 0;
  form.amount = Number(row.amount) || 0;
  form.passenger_count = row.passenger_count ?? 1;
  form.pay_type = row.pay_type || '微信';
  form.weather = row.weather || '晴';
  formVisible.value = true;
  formRef.value?.clearValidate();
}

async function submitForm() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  if (form.start_time && form.end_time && form.end_time < form.start_time) {
    ElMessage.warning('下车时间不能早于上车时间');
    return;
  }
  const payload = {
    vehicle_id: form.vehicle_id,
    driver_id: form.driver_id,
    pickup_region_id: form.pickup_region_id || null,
    dropoff_region_id: form.dropoff_region_id || null,
    start_time: form.start_time,
    end_time: form.end_time,
    loaded_mileage: form.loaded_mileage || 0,
    empty_mileage: form.empty_mileage || 0,
    amount: form.amount || 0,
    passenger_count: form.passenger_count || 1,
    pay_type: form.pay_type || '微信',
    weather: form.weather || '晴',
  };
  saving.value = true;
  try {
    if (form.id) {
      await operationApi.update(form.id, payload);
      ElMessage.success('订单修改成功');
    } else {
      await operationApi.create({ ...payload, order_no: form.order_no || null });
      ElMessage.success('订单创建成功');
    }
    formVisible.value = false;
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false;
  }
}

async function removeRow(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除订单「${row.order_no}」吗？删除后该订单的营运数据将无法恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }
  try {
    await operationApi.remove(row.id);
    ElMessage.success('删除成功');
    if (rows.value.length === 1 && query.page > 1) query.page -= 1;
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  }
}

/* ------------------------------------------------------------------ 导入 / 导出 */
function triggerImport() {
  uploadRef.value?.clearFiles?.();
  const input = uploadRef.value?.$el?.querySelector('input[type=file]');
  if (input) input.click();
}

async function handleImport(options) {
  const data = new FormData();
  data.append('file', options.file);
  loading.value = true;
  try {
    const result = (await operationApi.importExcel(data)) || {};
    importResult.value = result;
    errorRows.value = result.error_rows || [];
    errorMessages.value = result.error_messages || [];
    importVisible.value = true;
    ElMessage.success(`导入完成：成功 ${result.imported || 0} 行，跳过重复 ${result.duplicated || 0} 行`);
    await loadAll();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
    uploadRef.value?.clearFiles?.();
  }
}

function downloadTemplate() {
  downloadWithAuth(operationApi.templateUrl, 'operation_import_template.xlsx');
}

function exportData(fmt) {
  const condition = {
    start_date: filters.value.start_date,
    end_date: filters.value.end_date,
    vehicle_id: filters.value.vehicle_id,
    driver_id: filters.value.driver_id,
    region_id: filters.value.region_id,
    pay_type: filters.value.pay_type,
  };
  const filename = fmt === 'xlsx' ? 'operations.xlsx' : 'operations.csv';
  downloadWithAuth(operationApi.exportUrl({ fmt, ...condition }), filename);
  ElMessage.success(`已按当前筛选条件导出 ${fmt.toUpperCase()} 文件`);
}

onMounted(async () => {
  await loadOptions().catch(() => {});
  await loadAll();
});
</script>

<style scoped>
.filter-bar .el-form-item {
  margin-right: 12px;
}
.import-stat {
  background: #f7f9fc;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.import-stat__value {
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.import-stat__label {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 2px;
}
.import-scroll {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  padding: 10px;
  background: #fafbfd;
}
.import-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12.5px;
  color: #4b5563;
  padding: 4px 0;
  line-height: 1.6;
}
</style>
