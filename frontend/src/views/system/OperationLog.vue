<template>
  <div v-loading="loading">
    <PageHeader
      title="操作日志"
      description="系统自动记录所有写操作（新增、修改、删除），用于审计与问题追踪。"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选条件 -->
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="用户名 / 操作 / 请求路径"
        clearable
        style="width: 260px"
        @keyup.enter="search"
        @clear="search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select v-model="query.module" placeholder="全部模块" clearable style="width: 160px" @change="search">
        <el-option v-for="name in MODULES" :key="name" :label="name" :value="name" />
      </el-select>
      <el-select v-model="query.days" style="width: 150px" @change="search">
        <el-option v-for="item in DAY_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="search">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
    </div>

    <!-- 日志列表 -->
    <div class="table-card">
      <div class="table-toolbar">
        <span class="text-muted">共 {{ thousands(total) }} 条日志</span>
        <el-button type="danger" plain :icon="Delete" @click="openClear">清理历史日志</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="logs"
        border
        stripe
        empty-text="暂无操作日志"
        style="width: 100%"
      >
        <el-table-column prop="create_time" label="时间" width="175">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.create_time, true) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.username || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ row.module || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operation" label="操作" min-width="170" show-overflow-tooltip />
        <el-table-column prop="method" label="请求方法" width="105" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="methodTagType(row.method)" effect="light">
              {{ row.method }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="请求路径" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.path }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.ip || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_code" label="状态码" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="statusClass(row.status_code)">{{ row.status_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cost_ms" label="耗时(ms)" width="110" align="right">
          <template #default="{ row }">
            <span class="mono" :class="{ 'text-warning': row.cost_ms > 1000 }">
              {{ thousands(row.cost_ms) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="load"
          @current-change="load"
        />
      </div>
    </div>

    <!-- 清理历史日志 -->
    <el-dialog
      v-model="clearVisible"
      title="清理历史日志"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="150px">
        <el-form-item label="清理多少天以前">
          <el-input-number v-model="clearDays" :min="0" :max="3650" :step="1" />
          <span class="text-muted" style="margin-left: 10px; font-size: 12px">0 表示全部清空</span>
        </el-form-item>
      </el-form>
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        :title="
          clearDays > 0
            ? `将删除 ${clearDays} 天以前的全部操作日志`
            : '将删除全部操作日志（0 表示全部清空）'
        "
      >
        <template #default>
          <div style="font-size: 12.5px; line-height: 1.7">
            日志删除后不可恢复，审计痕迹将永久丢失，请确认后再执行。
          </div>
        </template>
      </el-alert>
      <template #footer>
        <el-button @click="clearVisible = false">取消</el-button>
        <el-button type="danger" :loading="clearing" @click="confirmClear">确定清理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Delete, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../../components/PageHeader.vue';
import { systemApi } from '../../api';
import { formatDateTime, thousands } from '../../utils/format';

const MODULES = [
  '认证',
  '区域管理',
  '车辆管理',
  '驾驶员管理',
  '人车绑定',
  '运营数据',
  '需求数据',
  '运营分析',
  '需求预测',
  '调度决策',
  '系统管理',
];

const DAY_OPTIONS = [
  { label: '近 1 天', value: 1 },
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
];

const loading = ref(false);
const clearing = ref(false);
const logs = ref([]);
const total = ref(0);
const clearVisible = ref(false);
const clearDays = ref(30);

const query = ref({ page: 1, page_size: 20, keyword: '', module: '', days: 30 });

function methodTagType(method) {
  return { GET: 'info', POST: 'success', PUT: 'warning', PATCH: 'warning', DELETE: 'danger' }[
    method
  ] || 'info';
}

function statusClass(code) {
  const value = Number(code);
  if (!Number.isFinite(value)) return '';
  if (value >= 500) return 'text-danger';
  if (value >= 400) return 'text-warning';
  if (value >= 200 && value < 300) return 'text-success';
  return '';
}

async function load() {
  loading.value = true;
  try {
    const data = await systemApi.logs({ ...query.value });
    logs.value = data.items || [];
    total.value = data.total || 0;
  } catch (error) {
    logs.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function search() {
  query.value.page = 1;
  load();
}

function resetQuery() {
  query.value = { page: 1, page_size: query.value.page_size, keyword: '', module: '', days: 30 };
  load();
}

function openClear() {
  clearDays.value = 30;
  clearVisible.value = true;
}

async function confirmClear() {
  const days = clearDays.value || 0;
  try {
    await ElMessageBox.confirm(
      days > 0
        ? `将永久删除 ${days} 天以前的全部操作日志，删除后不可恢复，确定继续吗？`
        : '将永久删除全部操作日志，删除后不可恢复，确定继续吗？',
      '清理历史日志',
      { type: 'warning', confirmButtonText: '确定清理', cancelButtonText: '取消' }
    );
  } catch (error) {
    return;
  }
  clearing.value = true;
  try {
    const result = await systemApi.clearLogs({ days });
    ElMessage.success(result?.message || '历史日志已清理');
    clearVisible.value = false;
    query.value.page = 1;
    load();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    clearing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.table-card :deep(.el-table) {
  font-size: 12.5px;
}
</style>
