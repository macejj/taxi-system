<template>
  <div v-loading="loading">
    <PageHeader
      title="参数配置"
      description="维护运营分析、调度决策、需求预测与预警提醒的业务阈值，保存后实时作用于数据分析预警、需求预测与调度决策模块。"
    >
      <template #extra>
        <span class="text-muted" style="font-size: 12px">如需恢复默认值，请重启后端服务</span>
        <el-button :icon="RefreshRight" :loading="reloading" @click="reload">重新载入配置</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-16"
      type="info"
      :closable="false"
      show-icon
      title="修改后的参数会立即覆盖后端内存中的配置并生效，无需重启服务；如需恢复默认值，请重启后端服务。"
    />

    <div v-if="!loading && !configs.length" class="chart-card">
      <el-empty description="暂无参数配置项" />
    </div>

    <div v-else class="chart-card">
      <el-tabs v-model="activeGroup">
        <el-tab-pane
          v-for="group in groups"
          :key="group.name"
          :label="group.name"
          :name="group.name"
        >
          <el-form label-width="200px" label-position="right" @submit.prevent>
            <el-form-item v-for="item in group.items" :key="item.config_key" :label="item.config_name">
              <div class="config-row">
                <div class="config-row__main">
                  <el-select
                    v-if="item.config_key === 'FORECAST_SELECT_METRIC'"
                    v-model="values[item.config_key]"
                    style="width: 260px"
                  >
                    <el-option label="RMSE（均方根误差）" value="rmse" />
                    <el-option label="MAE（平均绝对误差）" value="mae" />
                    <el-option label="MAPE（平均绝对百分比误差）" value="mape" />
                  </el-select>
                  <el-input-number
                    v-else-if="item.value_type === 'int'"
                    v-model="values[item.config_key]"
                    :step="1"
                    :precision="0"
                    style="width: 200px"
                  />
                  <el-input-number
                    v-else-if="item.value_type === 'float'"
                    v-model="values[item.config_key]"
                    :step="0.05"
                    :precision="2"
                    style="width: 200px"
                  />
                  <el-input
                    v-else
                    v-model="values[item.config_key]"
                    style="width: 260px"
                    placeholder="请输入配置值"
                  />
                  <el-tag size="small" type="info" effect="plain" class="config-key">
                    {{ item.config_key }}
                  </el-tag>
                </div>

                <el-button
                  type="primary"
                  plain
                  :loading="savingKey === item.config_key"
                  @click="save(item)"
                >
                  保存
                </el-button>
              </div>

              <div v-if="item.description" class="config-desc text-muted">
                {{ item.description }}
              </div>
              <div class="config-desc text-muted">
                最后更新：{{ formatDateTime(item.update_time, true) }}
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Refresh, RefreshRight } from '@element-plus/icons-vue';
import PageHeader from '../../components/PageHeader.vue';
import { systemApi } from '../../api';
import { formatDateTime } from '../../utils/format';

const loading = ref(false);
const reloading = ref(false);
const savingKey = ref('');
const configs = ref([]);
const values = ref({});
const activeGroup = ref('');

/** 按 config_group 分组，tab 名即分组名 */
const groups = computed(() => {
  const map = new Map();
  configs.value.forEach((item) => {
    const name = item.config_group || '其他';
    if (!map.has(name)) map.set(name, { name, items: [] });
    map.get(name).items.push(item);
  });
  return Array.from(map.values());
});

function castValue(valueType, raw) {
  if (valueType === 'int') {
    const num = Number.parseInt(raw, 10);
    return Number.isFinite(num) ? num : 0;
  }
  if (valueType === 'float') {
    const num = Number.parseFloat(raw);
    return Number.isFinite(num) ? num : 0;
  }
  return raw === null || raw === undefined ? '' : String(raw);
}

/** 把接口返回的配置写入本地表单模型 */
function syncValues() {
  const next = {};
  configs.value.forEach((item) => {
    next[item.config_key] = castValue(item.value_type, item.config_value);
  });
  values.value = next;
}

async function load() {
  loading.value = true;
  try {
    const data = await systemApi.configs();
    configs.value = data || [];
    syncValues();
    if (!activeGroup.value || !groups.value.some((group) => group.name === activeGroup.value)) {
      activeGroup.value = groups.value.length ? groups.value[0].name : '';
    }
  } catch (error) {
    configs.value = [];
    values.value = {};
  } finally {
    loading.value = false;
  }
}

async function reload() {
  reloading.value = true;
  try {
    const result = await systemApi.reloadConfigs();
    ElMessage.success(result?.message || '参数配置已重新载入');
    await load();
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    reloading.value = false;
  }
}

async function save(item) {
  const raw = values.value[item.config_key];
  if (raw === null || raw === undefined || raw === '') {
    ElMessage.warning(`请为「${item.config_name}」填写有效的配置值`);
    return;
  }
  savingKey.value = item.config_key;
  try {
    const updated = await systemApi.updateConfig(item.config_key, String(raw));
    // 以后端返回为准同步本地值
    if (updated && updated.config_key) {
      values.value[item.config_key] = castValue(updated.value_type, updated.config_value);
      const row = configs.value.find((config) => config.config_key === item.config_key);
      if (row) {
        row.config_value = updated.config_value;
        row.update_time = updated.update_time;
      }
    }
    ElMessage.success(`「${item.config_name}」已保存`);
  } catch (error) {
    /* 拦截器已提示 */
  } finally {
    savingKey.value = '';
  }
}

onMounted(load);
</script>

<style scoped>
.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.config-row__main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.config-key {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.config-desc {
  width: 100%;
  font-size: 12px;
  line-height: 1.7;
  margin-top: 2px;
}
</style>
