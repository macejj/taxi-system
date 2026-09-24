<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>出租车运营管理系统</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';
import { ElMessage } from 'element-plus';

const username = ref('');
const password = ref('');
const loading = ref(false);
const router = useRouter();

async function handleLogin() {
  loading.value = true;
  try {
    const res = await request.post('/auth/login', { username: username.value, password: password.value });
    localStorage.setItem('token', res.access_token);
    ElMessage.success('登录成功');
    router.push('/');
  } catch (e) {
    // 拦截器已处理错误
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 350px;
  text-align: center;
}
</style>