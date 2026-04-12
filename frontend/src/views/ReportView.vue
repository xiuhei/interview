<template>
  <div class="page-grid">
    <section class="panel-card report-hero">
      <div>
        <p class="eyebrow">面试总结</p>
        <h2>综合得分 {{ formatScore(report?.total_score) }} / 胜任度 {{ reportLevelLabel(report?.report_level) }}</h2>
        <p class="muted">{{ reportSummary(report) }}</p>
      </div>
      <el-button @click="handleBack">{{ report?.answer_mode === "audio" ? "返回面试首页" : "返回历史记录" }}</el-button>
    </section>

    <section v-if="!reportReady" class="panel-card section-card analysis-pending">
      <h3>AI 正在分析这场面试</h3>
      <p class="muted">普通面试已切换到异步分析流程。逐题评分、能力图谱和训练建议生成后会自动显示。</p>
    </section>

    <ReportCharts v-if="reportReady && report" :report="report" />

    <section v-if="reportReady && voiceScoreRows.length" class="panel-card section-card">
      <h3>语音维度评分</h3>
      <div class="voice-grid">
        <div v-for="item in voiceScoreRows" :key="item.label" class="voice-card">
          <strong>{{ item.label }}</strong>
          <span>{{ item.value }}</span>
        </div>
      </div>
    </section>

    <section v-if="reportReady" class="report-grid">
      <div class="panel-card section-card">
        <h3>改进建议</h3>
        <el-timeline>
          <el-timeline-item v-for="item in report?.suggestions" :key="item.issue">
            <strong>{{ item.issue }}</strong>
            <p>{{ item.reason }}</p>
            <p>{{ item.improvement }}</p>
            <p class="muted">推荐练习：{{ item.practice_direction }}</p>
          </el-timeline-item>
        </el-timeline>
      </div>
      <div class="panel-card section-card">
        <h3>下一步训练计划</h3>
        <el-steps direction="vertical" :active="report?.next_training_plan.length || 0">
          <el-step v-for="item in report?.next_training_plan" :key="item" :title="item" />
        </el-steps>
      </div>
    </section>

    <section class="panel-card section-card">
      <h3>{{ report?.answer_mode === "audio" ? "轮次摘要" : "题目记录" }}</h3>
      <p v-if="report?.answer_mode === 'audio'" class="muted">真实语音面试不进入历史档案，这里仅保留本次报告页可见的轮次摘要。</p>
      <el-table :data="report?.qa_records || []">
        <el-table-column prop="turn_no" label="轮次" width="80" />
        <el-table-column prop="question" label="问题" />
        <el-table-column label="得分" width="100">
          <template #default="scope">
            {{ formatScore(getNumberField(scope.row, "score")) }}
          </template>
        </el-table-column>
        <el-table-column label="追问依据">
          <template #default="scope">
            {{ translatedValue(getStringField(scope.row, "follow_up_reason")) }}
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import ReportCharts from "@/components/ReportCharts.vue";
import { fetchInterviewReport } from "@/api/interviews";
import type { InterviewReport } from "@/types/models";
import { isFallbackEnglishSummary, reportLevelLabel, scoreLabel, translatedValue } from "@/utils/display";

const route = useRoute();
const router = useRouter();
const report = ref<InterviewReport | null>(null);
const REFRESH_INTERVAL_MS = 1500;
let refreshTimer: number | null = null;

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "--";
}

function reportSummary(current: InterviewReport | null) {
  if (!current) return "";
  if (current.analysis_status === "pending") {
    return current.summary || "AI 正在分析你的面试，完整报告生成后会自动显示。";
  }
  if (current.summary && !isFallbackEnglishSummary(current.summary)) {
    return current.summary;
  }
  return `本场面试总分 ${formatScore(current.total_score)} 分，当前水平为“${reportLevelLabel(current.report_level)}”。`;
}

function handleBack() {
  if (report.value?.answer_mode === "audio") {
    router.push("/interviews/new");
    return;
  }
  router.push("/history");
}

function getNumberField(row: Record<string, unknown>, key: string) {
  const value = row[key];
  return typeof value === "number" ? value : null;
}

function getStringField(row: Record<string, unknown>, key: string) {
  const value = row[key];
  return typeof value === "string" ? value : "";
}

const voiceScoreRows = computed(() =>
  Object.entries(report.value?.voice_scores || {}).map(([key, value]) => ({
    label: scoreLabel(key),
    value: formatScore(value),
  })),
);

const reportReady = computed(() => report.value?.analysis_status !== "pending");

async function loadReport() {
  report.value = (await fetchInterviewReport(Number(route.params.id))).data;
  if (reportReady.value) {
    stopPolling();
  }
}

function stopPolling() {
  if (refreshTimer !== null) {
    window.clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

function scheduleRefresh() {
  stopPolling();
  if (reportReady.value) return;
  refreshTimer = window.setTimeout(async () => {
    await loadReport();
    scheduleRefresh();
  }, REFRESH_INTERVAL_MS);
}

onMounted(async () => {
  await loadReport();
  scheduleRefresh();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.report-hero,
.section-card {
  padding: 20px;
}

.report-grid {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 16px;
}

.voice-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.voice-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid var(--border);
}

.voice-card span {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
}

.analysis-pending {
  background: rgba(15, 118, 110, 0.06);
}

.muted {
  color: var(--muted);
}

@media (max-width: 960px) {
  .report-grid,
  .voice-grid {
    grid-template-columns: 1fr;
  }
}
</style>
