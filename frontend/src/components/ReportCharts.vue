<template>
  <div class="chart-grid">
    <div ref="radarRef" class="panel-card chart"></div>
    <div ref="barRef" class="panel-card chart"></div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";

import { useReportCharts } from "@/composables/useReportCharts";
import type { InterviewReport } from "@/types/models";

const props = defineProps<{ report: InterviewReport | null }>();
const radarRef = ref<HTMLDivElement | null>(null);
const barRef = ref<HTMLDivElement | null>(null);
const { renderBar, renderRadar } = useReportCharts();

async function render() {
  await nextTick();
  if (!props.report || !radarRef.value || !barRef.value) return;
  renderRadar(radarRef.value, props.report);
  renderBar(barRef.value, props.report);
}

onMounted(render);
watch(() => props.report, render);
</script>

<style scoped>
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.chart {
  min-height: 320px;
}
@media (max-width: 960px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
