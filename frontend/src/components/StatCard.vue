<template>
  <div class="stat-card" :class="`stat-card--${tone}`">
    <div class="stat-card__body">
      <div class="stat-card__label">
        {{ label }}
        <el-tooltip v-if="tip" :content="tip" placement="top">
          <el-icon class="stat-card__tip"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <div class="stat-card__value">
        <span class="stat-card__number">{{ displayValue }}</span>
        <span v-if="unit" class="stat-card__unit">{{ unit }}</span>
      </div>
      <div v-if="change !== null && change !== undefined" class="stat-card__change">
        <el-tag :type="changeTag.type" size="small" effect="light">
          {{ changeTag.text }}
        </el-tag>
        <span class="stat-card__change-label">{{ changeLabel }}</span>
      </div>
      <div v-else-if="sub" class="stat-card__sub">{{ sub }}</div>
    </div>
    <div class="stat-card__icon">
      <el-icon :size="26"><component :is="icon" /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { QuestionFilled } from '@element-plus/icons-vue';
import { changeInfo, thousands } from '../utils/format';

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  unit: { type: String, default: '' },
  icon: { type: [String, Object], default: 'DataLine' },
  tone: { type: String, default: 'blue' },
  digits: { type: Number, default: 0 },
  tip: { type: String, default: '' },
  sub: { type: String, default: '' },
  change: { type: [Number, null], default: null },
  changeLabel: { type: String, default: '较上期' },
  //: 指标「越低越好」时置 true（如空驶率）
  inverse: { type: Boolean, default: false },
});

const displayValue = computed(() => {
  if (typeof props.value === 'string') return props.value;
  return thousands(props.value, props.digits);
});

const changeTag = computed(() => changeInfo(props.change, props.inverse));
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: box-shadow 0.2s, transform 0.2s;
  height: 100%;
}
.stat-card:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
.stat-card__label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--app-text-secondary);
}
.stat-card__tip {
  cursor: help;
  font-size: 13px;
  color: #b8c0cc;
}
.stat-card__value {
  margin-top: 6px;
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.stat-card__number {
  font-size: 24px;
  font-weight: 600;
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-card__unit {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.stat-card__change,
.stat-card__sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.stat-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-card--blue .stat-card__icon {
  background: rgba(43, 109, 229, 0.1);
  color: #2b6de5;
}
.stat-card--green .stat-card__icon {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
}
.stat-card--orange .stat-card__icon {
  background: rgba(245, 158, 11, 0.14);
  color: #f59e0b;
}
.stat-card--red .stat-card__icon {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}
.stat-card--purple .stat-card__icon {
  background: rgba(139, 92, 246, 0.12);
  color: #8b5cf6;
}
.stat-card--cyan .stat-card__icon {
  background: rgba(6, 182, 212, 0.12);
  color: #06b6d4;
}
</style>
