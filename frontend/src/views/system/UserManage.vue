<template>
  <div v-loading="loading">
    <PageHeader
      title="用户管理"
      description="维护系统账号与角色权限：系统管理员可新增、编辑、重置密码与删除账号，其他角色只能查看。"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <el-alert class="mb-16" type="info" :closable="false" show-icon>
      <template #title>角色权限说明</template>
      <div class="role-tip">系统管理员（admin）：拥有全部权限，可管理账号、参数配置与数据维护。</div>
      <div class="role-tip">调度员（operator）：可管理运营数据并执行调度决策。</div>
      <div class="role-tip">只读用户（viewer）：仅能查看各模块数据，不能做任何修改。</div>
    </el-alert>

    <el-alert
      v-if="currentUser.id && !isAdmin"
      class="mb-16"
      type="warning"
      :closable="false"
      show-icon
      :title="`当前登录角色为「${ROLE_TEXT[currentUser.role] || currentUser.role}」，用户管理仅系统管理员可用，本页为只读。`"
    />

    <!-- 筛选条件 -->
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="用户名 / 真实姓名"
        clearable
        style="width: 220px"
        @keyup.enter="search"
        @clear="search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="query.role"
        placeholder="全部角色"
        clearable
        style="width: 150px"
        @change="search"
      >
        <el-option
          v-for="item in roleOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="query.status"
        placeholder="全部状态"
        clearable
        style="width: 130px"
        @change="search"
      >
        <el-option label="启用" :value="1" />
        <el-option label="禁用" :value="0" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="search">查询</el-button>
      <el-button :icon="RefreshLeft" @click="resetQuery">重置</el-button>
      <span class="text-muted" style="font-size: 12px">状态筛选在当前页结果中生效</span>
    </div>

    <!-- 账号列表 -->
    <div class="table-card">
      <div class="table-toolbar">
        <span class="text-muted">
          共 {{ thousands(total) }} 个账号，当前页显示 {{ displayUsers.length }} 条
        </span>
        <el-tooltip :disabled="isAdmin" content="仅系统管理员可新增用户" placement="top">
          <span>
            <el-button type="primary" :icon="Plus" :disabled="!isAdmin" @click="openCreate">
              新增用户
            </el-button>
          </span>
        </el-tooltip>
      </div>

      <el-table
        v-loading="loading"
        :data="displayUsers"
        border
        stripe
        empty-text="暂无账号数据"
        style="width: 100%"
      >
        <el-table-column prop="username" label="用户名" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.username }}</span>
            <el-tag
              v-if="isSelf(row)"
              size="small"
              type="success"
              effect="plain"
              style="margin-left: 6px"
            >
              当前登录
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="real_name" label="真实姓名" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.real_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" effect="light">
              {{ ROLE_TEXT[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="140">
          <template #default="{ row }">
            <span class="mono">{{ row.phone || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tooltip
              :disabled="!statusTip(row)"
              :content="statusTip(row)"
              placement="top"
            >
              <span>
                <el-switch
                  v-model="row.status"
                  :active-value="1"
                  :inactive-value="0"
                  :disabled="isSelf(row) || !isAdmin"
                  :loading="statusLoadingId === row.id"
                  @change="toggleStatus(row)"
                />
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录时间" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.last_login) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.create_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!isAdmin" @click="openEdit(row)">
              编辑
            </el-button>
            <el-button link type="primary" :disabled="!isAdmin" @click="openReset(row)">
              重置密码
            </el-button>
            <el-tooltip
              :disabled="!deleteTip(row)"
              :content="deleteTip(row)"
              placement="top"
            >
              <span>
                <el-button
                  link
                  type="danger"
                  :disabled="Boolean(deleteTip(row))"
                  @click="removeUser(row)"
                >
                  删除
                </el-button>
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
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

    <!-- 新增用户 -->
    <el-dialog v-model="createVisible" title="新增用户" width="520px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="2~30 位，登录时使用" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            placeholder="至少 4 位"
            show-password
          />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="createForm.real_name" placeholder="请输入真实姓名" clearable />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option
              v-for="item in roleOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="createForm.phone" placeholder="选填" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户 -->
    <el-dialog v-model="editVisible" title="编辑用户" width="520px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="editForm.real_name" placeholder="请输入真实姓名" clearable />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option
              v-for="item in roleOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" placeholder="选填" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="editForm.status"
            :active-value="1"
            :inactive-value="0"
            :disabled="editForm.id === currentUser.id"
            active-text="启用"
            inactive-text="禁用"
          />
          <span v-if="editForm.id === currentUser.id" class="text-muted" style="margin-left: 10px">
            不能禁用当前登录账号
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog
      v-model="resetVisible"
      title="重置密码"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-alert
        class="mb-16"
        type="warning"
        :closable="false"
        show-icon
        :title="`即将重置账号「${resetForm.username}」的登录密码，请及时通知本人。`"
      />
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="90px">
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetForm.new_password"
            type="password"
            placeholder="至少 6 位"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReset">确定重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Refresh, RefreshLeft, Search } from '@element-plus/icons-vue';
import PageHeader from '../../components/PageHeader.vue';
import { authApi, systemApi } from '../../api';
import { ROLE_TEXT, formatDateTime, thousands } from '../../utils/format';

const loading = ref(false);
const saving = ref(false);
const users = ref([]);
const total = ref(0);
const statusLoadingId = ref(null);
const currentUser = ref({});

const query = ref({ page: 1, page_size: 20, keyword: '', role: '', status: '' });

const createVisible = ref(false);
const editVisible = ref(false);
const resetVisible = ref(false);
const createFormRef = ref(null);
const editFormRef = ref(null);
const resetFormRef = ref(null);

const createForm = ref({ username: '', password: '', real_name: '', role: 'operator', phone: '' });
const editForm = ref({ id: null, username: '', real_name: '', role: 'operator', phone: '', status: 1 });
const resetForm = ref({ id: null, username: '', new_password: '' });

const roleOptions = Object.keys(ROLE_TEXT).map((value) => ({ value, label: ROLE_TEXT[value] }));

const phoneRule = { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的 11 位手机号', trigger: 'blur' };

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 30, message: '用户名长度需为 2~30 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, message: '密码至少 4 位', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  phone: [phoneRule],
};

const editRules = {
  real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  phone: [phoneRule],
};

const resetRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
  ],
};

const isAdmin = computed(() => currentUser.value.role === 'admin');

/** 状态筛选：后端用户接口未提供状态参数，这里在当前页结果上做过滤 */
const displayUsers = computed(() => {
  const status = query.value.status;
  if (status === '' || status === null || status === undefined) return users.value;
  return users.value.filter((item) => item.status === status);
});

function isSelf(row) {
  return Boolean(currentUser.value.id) && row.id === currentUser.value.id;
}

function roleTagType(role) {
  return { admin: 'danger', operator: 'primary', viewer: 'info' }[role] || 'info';
}

/** 返回启用开关被禁用的原因，空字符串表示可切换 */
function statusTip(row) {
  if (!isAdmin.value) return '仅系统管理员可修改账号状态';
  if (isSelf(row)) return '不能禁用当前登录账号';
  return '';
}

/** 返回删除按钮被禁用的原因，空字符串表示可删除 */
function deleteTip(row) {
  if (!isAdmin.value) return '仅系统管理员可删除账号';
  if (isSelf(row)) return '不能删除当前登录账号';
  if (row.username === 'admin') return '内置管理员账号不能删除';
  return '';
}

async function loadCurrentUser() {
  try {
    currentUser.value = await authApi.me();
  } catch (error) {
    /* 拦截器已提示 */
  }
}

async function load() {
  loading.value = true;
  try {
    const data = await systemApi.users({ ...query.value });
    users.value = data.items || [];
    total.value = data.total || 0;
  } catch (error) {
    users.value = [];
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
  query.value = { page: 1, page_size: query.value.page_size, keyword: '', role: '', status: '' };
  load();
}

async function toggleStatus(row) {
  const next = row.status;
  statusLoadingId.value = row.id;
  try {
    await systemApi.updateUser(row.id, { status: next });
    ElMessage.success(next === 1 ? `已启用账号 ${row.username}` : `已禁用账号 ${row.username}`);
  } catch (error) {
    row.status = next === 1 ? 0 : 1; // 失败回滚开关
  } finally {
    statusLoadingId.value = null;
  }
}

function openCreate() {
  createForm.value = { username: '', password: '', real_name: '', role: 'operator', phone: '' };
  createVisible.value = true;
  createFormRef.value?.clearValidate();
}

async function submitCreate() {
  if (!createFormRef.value) return;
  const valid = await createFormRef.value.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    await systemApi.createUser({ ...createForm.value });
    ElMessage.success('用户创建成功');
    createVisible.value = false;
    search();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false;
  }
}

function openEdit(row) {
  editForm.value = {
    id: row.id,
    username: row.username,
    real_name: row.real_name || '',
    role: row.role,
    phone: row.phone || '',
    status: row.status,
  };
  editVisible.value = true;
  editFormRef.value?.clearValidate();
}

async function submitEdit() {
  if (!editFormRef.value) return;
  const valid = await editFormRef.value.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    await systemApi.updateUser(editForm.value.id, {
      real_name: editForm.value.real_name,
      role: editForm.value.role,
      phone: editForm.value.phone,
      status: editForm.value.status,
    });
    ElMessage.success('用户信息已更新');
    editVisible.value = false;
    load();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false;
  }
}

function openReset(row) {
  resetForm.value = { id: row.id, username: row.username, new_password: '' };
  resetVisible.value = true;
  resetFormRef.value?.clearValidate();
}

async function submitReset() {
  if (!resetFormRef.value) return;
  const valid = await resetFormRef.value.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    await systemApi.resetPassword(resetForm.value.id, {
      new_password: resetForm.value.new_password,
    });
    ElMessage.success(`账号 ${resetForm.value.username} 的密码已重置`);
    resetVisible.value = false;
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false;
  }
}

async function removeUser(row) {
  try {
    await ElMessageBox.confirm('删除后该账号将无法登录，确定继续吗？', '删除账号', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    });
  } catch (error) {
    return;
  }
  loading.value = true;
  try {
    await systemApi.removeUser(row.id);
    ElMessage.success(`账号 ${row.username} 已删除`);
    if (users.value.length === 1 && query.value.page > 1) query.value.page -= 1;
    load();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadCurrentUser();
  load();
});
</script>

<style scoped>
.role-tip {
  font-size: 12.5px;
  line-height: 1.8;
}
</style>
