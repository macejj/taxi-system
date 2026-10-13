<template>
  <div class="login-page">
    <div class="login-page__left">
      <div class="login-page__brand">
        <div class="login-page__badge">TAXI</div>
        <h1>城市出租车运营管理与决策支持系统</h1>
        <p>运营管理 · 数据分析 · 需求预测 · 调度决策支持</p>
      </div>
      <ul class="login-page__features">
        <li v-for="item in features" :key="item.title">
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ item.desc }}</span>
          </div>
        </li>
      </ul>
    </div>

    <div class="login-page__right">
      <el-card class="login-card" shadow="never">
        <h2 class="login-card__title">账号登录</h2>
        <p class="login-card__sub">请输入账号信息进入系统</p>
        <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent>
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" clearable>
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              show-password
              @keyup.enter="handleLogin"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form>

        <el-divider><span class="text-muted" style="font-size: 12px">演示账号</span></el-divider>
        <div class="login-card__accounts">
          <el-tag
            v-for="account in demoAccounts"
            :key="account.username"
            :type="account.type"
            effect="plain"
            style="cursor: pointer"
            @click="fillAccount(account)"
          >
            {{ account.label }}：{{ account.username }} / {{ account.password }}
          </el-tag>
        </div>
      </el-card>
      <p class="login-page__footer">© {{ year }} 毕业设计 · 出租车运营管理与决策支持系统</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { authApi } from '../api';

const router = useRouter();
const route = useRoute();
const formRef = ref(null);
const loading = ref(false);
const year = new Date().getFullYear();

const form = reactive({ username: 'admin', password: 'admin123' });

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
};

const features = [
  { icon: 'Van', title: '运营管理', desc: '车辆、驾驶员、排班、订单与叫车需求全流程' },
  { icon: 'TrendCharts', title: '数据分析', desc: 'KPI、趋势、区域热度、里程利用率与绩效排行' },
  { icon: 'MagicStick', title: '需求预测', desc: '多种时序模型滚动回测自动选优，输出未来逐时需求' },
  { icon: 'Guide', title: '调度决策', desc: '供需缺口测算与匈牙利最优指派，支持执行与效果评估' },
];

const demoAccounts = [
  { label: '管理员', username: 'admin', password: 'admin123', type: 'danger' },
  { label: '调度员', username: 'dispatcher', password: 'disp123', type: 'primary' },
  { label: '只读', username: 'viewer', password: 'view123', type: 'info' },
];

function fillAccount(account) {
  form.username = account.username;
  form.password = account.password;
}

async function handleLogin() {
  try {
    await formRef.value.validate();
  } catch (error) {
    return;
  }
  loading.value = true;
  try {
    const res = await authApi.login({ username: form.username, password: form.password });
    localStorage.setItem('token', res.access_token);
    try {
      const me = await authApi.me();
      localStorage.setItem('role', me.role || '');
    } catch (error) {
      localStorage.removeItem('role');
    }
    ElMessage.success('登录成功');
    router.push(route.query.redirect || '/dashboard');
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  height: 100vh;
  background: #f4f6fa;
}

.login-page__left {
  flex: 1.15;
  background: linear-gradient(150deg, #1b2a41 0%, #24405f 55%, #2b6de5 140%);
  color: #fff;
  padding: 60px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.login-page__left::after {
  content: '';
  position: absolute;
  width: 460px;
  height: 460px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(43, 109, 229, 0.45), transparent 70%);
  right: -160px;
  bottom: -160px;
}

.login-page__brand h1 {
  font-size: 26px;
  margin: 22px 0 10px;
  line-height: 1.45;
  font-weight: 600;
}

.login-page__brand p {
  margin: 0;
  opacity: 0.72;
  font-size: 14px;
  letter-spacing: 1px;
}

.login-page__badge {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #2b6de5, #06b6d4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 1px;
}

.login-page__features {
  list-style: none;
  padding: 0;
  margin: 46px 0 0;
  display: grid;
  gap: 18px;
  position: relative;
  z-index: 1;
}

.login-page__features li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.login-page__features strong {
  display: block;
  font-size: 14px;
  margin-bottom: 3px;
}

.login-page__features span {
  font-size: 12.5px;
  opacity: 0.68;
  line-height: 1.6;
}

.login-page__right {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  width: 380px;
  border-radius: 14px;
  border: 1px solid #e6eaf0;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.07);
  padding: 10px 8px;
}

.login-card__title {
  margin: 0 0 4px;
  font-size: 20px;
  text-align: center;
}

.login-card__sub {
  margin: 0 0 22px;
  text-align: center;
  font-size: 13px;
  color: #6b7280;
}

.login-card__accounts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.login-page__footer {
  margin-top: 18px;
  font-size: 12px;
  color: #9aa4b2;
}

@media (max-width: 900px) {
  .login-page__left {
    display: none;
  }
}
</style>
