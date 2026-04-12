<template>
  <section class="panel-card growth-panel">
    <div class="header-row">
      <div>
        <p class="eyebrow">成长趋势</p>
        <h3>个人成长与进步</h3>
        <p class="muted">{{ insight?.summary.narrative || emptyText }}</p>
      </div>
      <div class="status-pill">{{ insight?.summary.readiness_label || "待开始" }}</div>
    </div>

    <div v-if="insight && insight.summary.completed_sessions > 0" class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">已完成面试</span>
        <strong>{{ insight.summary.completed_sessions }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">平均得分</span>
        <strong>{{ formatScore(insight.summary.average_score) }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">最近一场</span>
        <strong>{{ formatScore(insight.summary.latest_score) }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">最近波动</span>
        <strong :class="deltaClass(insight.summary.score_delta)">{{ formatDelta(insight.summary.score_delta) }}</strong>
      </div>
    </div>

    <div v-if="insight && insight.summary.completed_sessions > 0" class="growth-grid">
      <div class="chart-stack">
        <div ref="trendRef" class="chart-card"></div>
        <div ref="competencyRef" class="chart-card"></div>
      </div>

      <div class="insight-stack">
        <div class="insight-card">
          <h4>能力总结</h4>
          <p><strong>当前优势：</strong>{{ competencyLabel(insight.summary.strongest_competency, "暂无") }}</p>
          <p><strong>重点补强：</strong>{{ competencyLabel(insight.summary.focus_competency) }}</p>
          <div class="tag-row">
            <el-tag v-for="item in insight.weaknesses.slice(0, 3)" :key="item.tag" class="tag" effect="plain">
              {{ competencyLabel(item.tag, item.tag) }} × {{ item.count }}
            </el-tag>
          </div>
        </div>

        <div class="insight-card">
          <h4>提升建议</h4>
          <ol class="plan-list">
            <li v-for="item in insight.summary.recommendations" :key="item">{{ item }}</li>
          </ol>
        </div>
      </div>
    </div>

    <div v-else class="empty-card">
      <p>{{ emptyText }}</p>
      <p class="muted">只有已完成的面试会进入趋势图、历史记录和个人总结，待完成或已过期的面试不会计入。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ECharts } from "echarts";

import { useGrowthCharts } from "@/composables/useGrowthCharts";
import type { GrowthInsight } from "@/types/models";
import { competencyLabel as formatCompetencyLabel } from "@/utils/display";

const props = defineProps<{
  insight: GrowthInsight | null;
}>();

const emptyText = "当前还没有可统计的已完成面试。完成一轮面试后，这里会展示你的能力趋势和训练建议。";
const trendRef = ref<HTMLDivElement | null>(null);
const competencyRef = ref<HTMLDivElement | null>(null);
const charts = ref<ECharts[]>([]);
const { renderCompetency, renderTrend } = useGrowthCharts();

function competencyLabel(value?: string | null, fallback = "综合能力") {
  if (!value) return fallback;
  return formatCompetencyLabel(value);
}

function destroyCharts() {
  charts.value.forEach((chart) => chart.dispose());
  charts.value = [];
}

async function renderCharts() {
  destroyCharts();
  await nextTick();
  if (!props.insight || props.insight.summary.completed_sessions === 0 || !trendRef.value || !competencyRef.value) return;
  charts.value = [renderTrend(trendRef.value, props.insight), renderCompetency(competencyRef.value, props.insight)];
}

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "--";
}

function formatDelta(value?: number | null) {
  if (typeof value !== "number") return "--";
  return value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}

function deltaClass(value?: number | null) {
  if (typeof value !== "number") return "neutral";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

onMounted(renderCharts);
watch(() => props.insight, renderCharts, { deep: true });
onBeforeUnmount(destroyCharts);
</script>

<style scoped>
.growth-panel {
  padding: 24px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.summary-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card,
.insight-card,
.empty-card,
.chart-card {
  border-radius: 20px;
  border: 1px solid rgba(30, 60, 110, 0.08);
  background: rgba(255, 255, 255, 0.64);
}

.summary-card {
  padding: 16px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
}

.summary-label {
  color: var(--muted);
  font-size: 12px;
}

.growth-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 16px;
}

.chart-stack,
.insight-stack {
  display: grid;
  gap: 16px;
}

.chart-card {
  min-height: 280px;
}

.insight-card,
.empty-card {
  padding: 18px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.tag {
  margin: 0;
}

.plan-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}

.status-pill {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(90, 169, 255, 0.10);
  color: var(--primary);
  font-weight: 600;
  white-space: nowrap;
}

.muted {
  color: var(--muted);
}

.up {
  color: var(--primary);
}

.down {
  color: var(--accent);
}

.neutral {
  color: var(--ink);
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .growth-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .header-row {
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
