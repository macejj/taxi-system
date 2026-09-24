<template>
  <el-container>
    <el-header style="background:#409EFF;color:white;display:flex;align-items:center;">
      <h3>出租车运营管理系统</h3>
      <el-button style="margin-left:auto" @click="logout">退出登录</el-button>
    </el-header>
    <el-container>
      <el-aside width="200px">
        <el-menu router :default-active="$route.path">
          <el-menu-item index="/vehicles">车辆管理</el-menu-item>
          <el-menu-item index="/drivers">驾驶员管理</el-menu-item>
          <el-menu-item index="/operations">数据导入</el-menu-item>
          <el-menu-item index="/analysis">数据分析</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

const router = useRouter();
function logout() {
  localStorage.removeItem('token');
  ElMessage.success('已退出');
  router.push('/login');
}
</script>