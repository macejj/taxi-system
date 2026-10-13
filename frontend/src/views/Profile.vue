<template>
  <div v-loading="loading">
    <PageHeader title="个人中心" description="查看当前登录账号的基本信息、修改登录密码并了解系统版本与技术栈。">
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadUser">刷新</el-button>
        <el-button type="primary" plain @click="openDocs">
          <el-icon><Document /></el-icon>
          接口文档
        </el-button>
      </template>
    </PageHeader>

    <el-row :gutter="14" class="mb-16">
      <!-- 账号信息 -->
      <el-col :xs="24" :md="9">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">账号信息</div>
            <el-tag :type="user.status === 1 ? 'success' : 'info'" size="small" effect="light">
              {{ user.status === 1 ? '正常' : '已停用' }}
            </el-tag>
          </div>

          <div class="profile-user">
            <div class="profile-avatar">{{ avatarText }}</div>
            <div class="profile-user__main">
              <div class="profile-user__name">{{ user.real_name || user.username || '未登录' }}</div>
              <div class="profile-user__role">{{ roleText }}</div>
            </div>
          </div>

          <el-descriptions :column="1" size="small" border class="mt-16">
            <el-descriptions-item label="用户名">{{ user.username || '-' }}</el-descriptions-item>
            <el-descriptions-item label="真实姓名">{{ user.real_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag size="small" effect="plain">{{ roleText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="手机号">
              <span class="mono">{{ user.phone || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="最后登录">
              {{ formatDateTime(user.last_login, true) }}
            </el-descriptions-item>
          </el-descriptions>

          <p class="chart-card__desc">
            角色权限：系统管理员可维护基础数据与参数；调度员可生成调度方案；只读用户仅可查看。
          </p>
        </div>
      </el-col>

      <!-- 修改密码 -->
      <el-col :xs="24" :md="15">
        <div class="chart-card">
          <div class="chart-card__head">
            <div class="chart-card__title">修改密码</div>
            <span class="text-muted" style="font-size: 12px">修改成功后需要重新登录</span>
          </div>

          <el-form
            ref="pwdFormRef"
            :model="pwdForm"
            :rules="pwdRules"
            label-width="100px"
            class="pwd-form"
            @submit.prevent
          >
            <el-form-item label="原密码" prop="old_password">
              <el-input
                v-model="pwdForm.old_password"
                type="password"
                placeholder="请输入当前登录密码"
                show-password
                clearable
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="pwdForm.new_password"
                type="password"
                placeholder="至少 6 位，建议字母与数字组合"
                show-password
                clearable
              >
                <template #prefix>
                  <el-icon><Key /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input
                v-model="pwdForm.confirm_password"
                type="password"
                placeholder="请再次输入新密码"
                show-password
                clearable
                @keyup.enter="submitPassword"
              >
                <template #prefix>
                  <el-icon><Key /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submitPassword">
                确认修改
              </el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>

          <el-alert
            title="安全提示"
            type="info"
            :closable="false"
            show-icon
            description="请勿使用与用户名相同或过于简单的密码；修改密码后当前登录令牌将失效。"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 系统信息 -->
    <div class="chart-card">
      <div class="chart-card__head">
        <div class="chart-card__title">系统信息</div>
        <el-button type="primary" size="small" @click="openDocs">
          <el-icon><Document /></el-icon>
          查看后端接口文档
        </el-button>
      </div>

      <el-descriptions :column="2" size="small" border>
        <el-descriptions-item label="系统名称">城市出租车运营管理与决策支持系统</el-descriptions-item>
        <el-descriptions-item label="版本">v1.0.0（毕业设计版）</el-descriptions-item>
        <el-descriptions-item label="技术栈" :span="2">
          Vue 3 + Element Plus + ECharts / FastAPI + SQLAlchemy + MySQL
        </el-descriptions-item>
        <el-descriptions-item label="前端构建">Vite 5 + Vue Router 4（组合式 API）</el-descriptions-item>
        <el-descriptions-item label="图表引擎">Apache ECharts 5</el-descriptions-item>
        <el-descriptions-item label="后端服务">FastAPI（Swagger 文档路径 /docs）</el-descriptions-item>
        <el-descriptions-item label="数据范围">运营区域 · 车辆 · 驾驶员 · 叫车需求 · 营运订单 · 调度方案</el-descriptions-item>
      </el-descriptions>

      <p class="chart-card__desc">
        接口文档由 FastAPI 自动生成，可在线调试各业务接口；生产部署时建议关闭或限制访问权限。
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Refresh } from '@element-plus/icons-vue';
import PageHeader from '../components/PageHeader.vue';
import { authApi } from '../api';
import { ROLE_TEXT, formatDateTime } from '../utils/format';

const router = useRouter();
const loading = ref(false);
const submitting = ref(false);
const user = ref({});
const pwdFormRef = ref(null);

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
});

const pwdRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 32, message: '新密码长度需为 6 ~ 32 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error('请再次输入新密码'));
        } else if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的新密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur',
    },
  ],
};

const roleText = computed(() => ROLE_TEXT[user.value.role] || user.value.role || '-');

const avatarText = computed(() => {
  const name = user.value.real_name || user.value.username || '?';
  return String(name).slice(0, 1).toUpperCase();
});

async function loadUser() {
  loading.value = true;
  try {
    const data = await authApi.me();
    user.value = data || {};
  } catch (error) {
    /* 拦截器已统一提示 */
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  pwdForm.old_password = '';
  pwdForm.new_password = '';
  pwdForm.confirm_password = '';
  if (pwdFormRef.value) pwdFormRef.value.clearValidate();
}

async function submitPassword() {
  try {
    await pwdFormRef.value.validate();
  } catch (error) {
    return;
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致');
    return;
  }
  submitting.value = true;
  try {
    await authApi.changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    });
    ElMessage.success('密码修改成功，请重新登录');
    localStorage.removeItem('token');
    resetForm();
    router.push('/login');
  } catch (error) {
    /* 拦截器已统一提示（原密码错误等） */
  } finally {
    submitting.value = false;
  }
}

function openDocs() {
  window.open('/docs', '_blank');
}

onMounted(() => {
  loadUser();
});
</script>

<style scoped>
.profile-user {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 12px;
  border-radius: 10px;
  background: #f7f9fc;
}
.profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2b6de5, #06b6d4);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  flex-shrink: 0;
}
.profile-user__main {
  min-width: 0;
}
.profile-user__name {
  font-size: 17px;
  font-weight: 600;
  color: var(--app-text);
  line-height: 1.3;
}
.profile-user__role {
  font-size: 12.5px;
  color: var(--app-text-secondary);
  margin-top: 4px;
}
.pwd-form {
  max-width: 460px;
}
</style>
