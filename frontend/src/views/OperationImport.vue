<template>
  <div>
    <h3>运营数据导入</h3>
    <el-upload
      :http-request="uploadFile"
      accept=".xlsx,.xls"
      :show-file-list="false"
    >
      <el-button type="primary">选择 Excel 文件上传</el-button>
    </el-upload>
    <div v-if="result" style="margin-top:20px">
      <p>成功导入：{{ result.imported }} 条</p>
      <p v-if="result.error_rows && result.error_rows.length">错误行号：{{ result.error_rows.join(', ') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import request from '../api/request';
import { ElMessage } from 'element-plus';

const result = ref(null);

async function uploadFile(options) {
  const formData = new FormData();
  formData.append('file', options.file);
  try {
    const res = await request.post('/operation/import-excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    result.value = res;
    ElMessage.success('导入完成');
  } catch (e) {
    // 拦截器已处理
  }
}
</script>