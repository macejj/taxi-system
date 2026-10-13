<template>
  <div class="page-header">
    <div class="page-header__main">
      <h2 class="page-header__title">{{ title }}</h2>
      <p v-if="description" class="page-header__desc">{{ description }}</p>
    </div>
    <div class="page-header__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
});
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.page-header__title {
  margin: 0;
  font-size: 19px;
  font-weight: 600;
  color: var(--app-text);
}
.page-header__desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--app-text-secondary);
  line-height: 1.6;
  max-width: 900px;
}
.page-header__extra {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
