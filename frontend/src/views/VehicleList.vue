<template>
  <div>
    <el-button type="primary" @click="openDialog">新增车辆</el-button>
    <el-table :data="vehicles" style="width: 100%">
      <el-table-column prop="plate_number" label="车牌号" />
      <el-table-column prop="brand_model" label="品牌型号" />
      <el-table-column prop="color" label="颜色" />
      <el-table-column prop="status" label="状态">
        <template #default="{ row }">
          {{ row.status === 1 ? '在营' : '停运' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="editVehicle(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteVehicle(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑车辆' : '新增车辆'">
      <el-form :model="form" label-width="80px">
        <el-form-item label="车牌号">
          <el-input v-model="form.plate_number" />
        </el-form-item>
        <el-form-item label="品牌型号">
          <el-input v-model="form.brand_model" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-input v-model="form.color" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="在营" :value="1" />
            <el-option label="停运" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveVehicle">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import request from '../api/request';
import { ElMessage } from 'element-plus';

const vehicles = ref([]);
const dialogVisible = ref(false);
const form = ref({});
const editId = ref(null);

async function fetchVehicles() {
  const data = await request.get('/vehicle/');
  vehicles.value = data;
}

function openDialog() {
  form.value = { status: 1 };
  editId.value = null;
  dialogVisible.value = true;
}

function editVehicle(row) {
  form.value = { ...row };
  editId.value = row.id;
  dialogVisible.value = true;
}

async function saveVehicle() {
  try {
    if (editId.value) {
      await request.put(`/vehicle/${editId.value}`, form.value);
    } else {
      await request.post('/vehicle/', form.value);
    }
    ElMessage.success('保存成功');
    dialogVisible.value = false;
    fetchVehicles();
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function deleteVehicle(id) {
  try {
    await request.delete(`/vehicle/${id}`);
    ElMessage.success('删除成功');
    fetchVehicles();
  } catch (e) {
    // 错误已由拦截器处理
  }
}

onMounted(fetchVehicles);
</script>