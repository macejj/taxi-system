<template>
  <div>
    <el-date-picker
      v-model="dateRange"
      type="daterange"
      value-format="YYYY-MM-DD"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      @change="fetchData"
    />
    <div ref="chartRef" style="height: 400px; margin-top: 20px;"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import request from '../api/request';

const dateRange = ref([]);
const chartRef = ref(null);
let chart = null;

async function fetchData() {
  if (!dateRange.value || dateRange.value.length !== 2) return;
  const [start, end] = dateRange.value;
  const data = await request.get('/analysis/income-summary', {
    params: { start_date: start, end_date: end, group_by: 'day' }
  });
  const dates = data.map(d => d.date);
  const amounts = data.map(d => d.total_amount);
  const counts = data.map(d => d.order_count);

  if (!chart) {
    chart = echarts.init(chartRef.value);
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['收入', '订单量'] },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: '收入(元)' },
      { type: 'value', name: '订单量' }
    ],
    series: [
      { name: '收入', type: 'line', data: amounts, yAxisIndex: 0 },
      { name: '订单量', type: 'bar', data: counts, yAxisIndex: 1 }
    ]
  });
}

onMounted(() => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 7);
  dateRange.value = [start.toISOString().slice(0,10), end.toISOString().slice(0,10)];
  fetchData();
});
</script>