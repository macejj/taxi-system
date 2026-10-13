<template>
  <div class="chart-box" :style="{ height: typeof height === 'number' ? `${height}px` : height }">
    <div ref="chartRef" class="chart-canvas" />
    <div v-if="empty && !loading" class="chart-empty">
      <el-empty :description="emptyText" :image-size="60" />
    </div>
    <div v-if="loading" class="chart-loading" v-loading="true" element-loading-text="加载中..." />
  </div>
</template>

<script setup>
/**
 * 通用 ECharts 容器：
 * - 自动初始化 / 销毁实例
 * - 监听容器尺寸变化自动 resize
 * - option 变化时增量更新（notMerge 可关闭）
 * - 内置空数据与加载态
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  option: { type: Object, default: () => ({}) },
  height: { type: [Number, String], default: 320 },
  loading: { type: Boolean, default: false },
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无数据' },
  notMerge: { type: Boolean, default: false },
});

const chartRef = ref(null);
const chart = shallowRef(null);
let observer = null;

function render() {
  if (!chart.value) return;
  chart.value.setOption(props.option || {}, props.notMerge);
}

function resize() {
  chart.value?.resize();
}

onMounted(() => {
  chart.value = echarts.init(chartRef.value);
  render();
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(resize);
    observer.observe(chartRef.value);
  } else {
    window.addEventListener('resize', resize);
  }
});

onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener('resize', resize);
  chart.value?.dispose();
  chart.value = null;
});

watch(() => props.option, render, { deep: true });
watch(
  () => props.loading,
  (value) => {
    if (!value) requestAnimationFrame(resize);
  }
);

defineExpose({ resize, getInstance: () => chart.value });
</script>

<style scoped>
.chart-box {
  position: relative;
  width: 100%;
}
.chart-canvas {
  width: 100%;
  height: 100%;
}
.chart-empty,
.chart-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.75);
}
</style>
