<template>
  <div>
    <el-button type="primary" @click="openDialog">新增驾驶员</el-button>
    <el-table :data="drivers" style="width: 100%">
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="gender" label="性别" />
      <el-table-column prop="id_card" label="身份证号" />
      <el-table-column prop="license_no" label="驾驶证号" />
      <el-table-column prop="phone" label="联系电话" />
      <el-table-column prop="status" label="状态">
        <template #default="{ row }">
          {{ row.status === 1 ? '在职' : '离职' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="editDriver(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteDriver(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑驾驶员' : '新增驾驶员'">
      <el-form :model="form" label-width="100px">
        <el-form-item label="姓名">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender">
            <el-option label="男" value="M" />
            <el-option label="女" value="F" />
          </el-select>
        </el-form-item>
        <el-form-item label="身份证号">
          <el-input v-model="form.id_card" />
        </el-form-item>
        <el-form-item label="驾驶证号">
          <el-input v-model="form.license_no" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="在职" :value="1" />
            <el-option label="离职" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDriver">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import request from '../api/request';
import { ElMessage } from 'element-plus';

const drivers = ref([]);
const dialogVisible = ref(false);
const form = ref({});
const editId = ref(null);

async function fetchDrivers() {
  const data = await request.get('/driver/');
  drivers.value = data;
}

function openDialog() {
  form.value = { status: 1, gender: 'M' };
  editId.value = null;
  dialogVisible.value = true;
}

function editDriver(row) {
  form.value = { ...row };
  editId.value = row.id;
  dialogVisible.value = true;
}

async function saveDriver() {
  try {
    if (editId.value) {
      await request.put(`/driver/${editId.value}`, form.value);
    } else {
      await request.post('/driver/', form.value);
    }
    ElMessage.success('保存成功');
    dialogVisible.value = false;
    fetchDrivers();
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function deleteDriver(id) {
  try {
    await request.delete(`/driver/${id}`);
    ElMessage.success('删除成功');
    fetchDrivers();
  } catch (e) {
    // 错误已由拦截器处理
  }
}

onMounted(fetchDrivers);
</script>