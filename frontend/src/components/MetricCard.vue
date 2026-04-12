<template>
  <div class="panel-card metric-card">
    <p class="label">{{ label }}</p>
    <h3>{{ value }}</h3>
    <p class="hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  value: string | number;
  hint: string;
}>();
</script>

<style scoped>
.metric-card {
  padding: 20px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.86), rgba(245, 239, 230, 0.66));
}

.label {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

h3 {
  margin: 10px 0 8px;
  font-size: clamp(28px, 4vw, 34px);
}

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}
</style>
