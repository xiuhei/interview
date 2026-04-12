<template>
  <div class="page-grid" v-if="detail">
    <section class="panel-card archive-hero">
      <div>
        <p class="eyebrow">面试档案</p>
        <h2>{{ detail.title }}</h2>
        <p class="muted">{{ archiveSummary(detail) }}</p>
      </div>
      <div class="hero-actions">
        <el-button @click="router.push('/history')">返回历史记录</el-button>
        <el-button type="danger" plain @click="handleDelete">删除面试记录</el-button>
      </div>
    </section>

    <section class="panel-card section-card">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="岗位">{{ positionLabel(detail.position) }}</el-descriptions-item>
        <el-descriptions-item label="面试风格">{{ styleLabel(detail.style) }}</el-descriptions-item>
        <el-descriptions-item label="回答方式">{{ answerModeLabel(detail.answer_mode) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(detail.completed_at) }}</el-descriptions-item>
        <el-descriptions-item label="总分">{{ formatScore(detail.total_score) }}</el-descriptions-item>
        <el-descriptions-item label="等级">{{ reportLevelLabel(detail.report_level) }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <ReportCharts v-if="detail.report_ready" :report="detail" />

    <section v-else class="panel-card section-card analysis-pending">
      <h3>AI 正在分析你的面试</h3>
      <p class="muted">语音转写、逐题评分和综合报告还在生成中。你已经可以先查看全部问答记录，稍后刷新页面即可看到完整结果。</p>
    </section>

    <section class="detail-grid">
      <div class="panel-card section-card">
        <h3>能力维度评分表</h3>
        <el-table :data="competencyRows">
          <el-table-column prop="competency" label="能力维度" />
          <el-table-column prop="score" label="得分" width="120" />
        </el-table>
      </div>

      <div class="panel-card section-card">
        <h3>改进建议</h3>
        <el-timeline>
          <el-timeline-item v-for="item in detail.suggestions" :key="item.issue">
            <strong>{{ item.issue }}</strong>
            <p>{{ item.reason }}</p>
            <p>{{ item.improvement }}</p>
            <p class="muted">推荐练习：{{ item.practice_direction }}</p>
          </el-timeline-item>
        </el-timeline>
      </div>
    </section>

    <section class="panel-card section-card">
      <div class="header-row">
        <h3>面试问答档案</h3>
        <span class="muted">共 {{ detail.questions.length }} 条记录</span>
      </div>

      <el-collapse v-model="expandedQuestions" class="question-stack">
        <el-collapse-item
          v-for="item in detail.questions"
          :key="item.question_id"
          :name="String(item.question_id)"
          class="question-card"
        >
          <template #title>
            <div class="question-header">
              <div>
                <strong>{{ timelineLabel(item) }}</strong>
                <p class="muted">能力维度：{{ competencyLabel(item.competency_code) }} · 回答时间：{{ formatDateTime(item.answered_at) }}</p>
              </div>
              <div class="question-meta">
                <span class="mode-pill">{{ answerModeLabel(item.answer_mode || detail.answer_mode) }}</span>
                <div class="score-pill">{{ formatScore(item.overall_score) }}</div>
              </div>
            </div>
          </template>

          <div class="content-panel prompt-block">
            <p class="block-label">面试官提问</p>
            <p class="content-text">{{ item.question_text }}</p>
          </div>

          <div class="content-panel answer-block">
            <div class="block-head">
              <p class="block-label">用户回答</p>
              <span v-if="item.answer_mode === 'audio' && item.audio_duration_seconds" class="block-meta">
                语音时长：{{ formatDuration(item.audio_duration_seconds) }}
              </span>
            </div>
            <p class="content-text preserve">{{ primaryAnswerText(item) }}</p>
            <audio
              v-if="item.answer_mode === 'audio' && item.audio_path"
              class="audio-player"
              :src="resolveAudioUrl(item.audio_path)"
              controls
              preload="none"
            />
            <p v-else-if="item.answer_mode === 'audio'" class="muted">未找到语音文件</p>
          </div>

          <div v-if="shouldShowTranscript(item)" class="content-panel transcript-block">
            <p class="block-label">语音转写</p>
            <p class="content-text preserve">{{ item.asr_text }}</p>
          </div>

          <div v-if="!item.evaluation_ready" class="content-panel status-block pending-inline">
            <p class="block-label">评分状态</p>
            <p class="content-text">AI 正在分析这一题，语音流畅度、清晰度、回答准确度等评分生成后会自动显示。</p>
          </div>

          <div v-if="item.evaluation_ready" class="score-grid">
            <div class="score-card">
              <div class="score-card-head">
                <h4>文本评分</h4>
                <span class="score-caption">聚焦回答内容本身</span>
              </div>
              <el-table :data="scoreRows(item.text_scores)" size="small" table-layout="auto">
                <el-table-column prop="label" label="维度" />
                <el-table-column prop="value" label="分数" width="100" />
              </el-table>
            </div>

            <div v-if="showAudioSection(item)" class="score-card">
              <div class="score-card-head">
                <h4>语言表达评分</h4>
                <span class="score-caption">保留核心语音表现指标</span>
              </div>
              <el-table :data="scoreRows(item.audio_scores)" size="small" table-layout="auto">
                <el-table-column prop="label" label="维度" />
                <el-table-column prop="value" label="分数" width="100" />
              </el-table>

              <div v-if="audioFeatureRows(item).length" class="audio-metrics">
                <div v-for="feature in audioFeatureRows(item)" :key="feature.label" class="metric-chip">
                  <span>{{ feature.label }}</span>
                  <strong>{{ feature.value }}</strong>
                </div>
              </div>
            </div>
          </div>

          <div v-if="item.evaluation_ready" class="content-panel explanation-block">
            <p class="block-label">评分说明</p>
            <p class="content-text">{{ item.explanation || "暂无评分说明" }}</p>
          </div>

          <div v-if="item.evaluation_ready && item.suggestions.length" class="content-panel feedback-block">
            <p class="block-label">改进建议</p>
            <ul class="suggestion-list">
              <li v-for="suggestion in item.suggestions" :key="suggestion">{{ suggestion }}</li>
            </ul>
          </div>
        </el-collapse-item>
      </el-collapse>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import ReportCharts from "@/components/ReportCharts.vue";
import { deleteHistory, fetchHistoryDetail } from "@/api/interviews";
import type { AudioFeatureSummary, HistoryInterviewDetail, HistoryQuestionRecord } from "@/types/models";
import {
  answerModeLabel,
  competencyLabel,
  interviewStatusLabel as statusLabel,
  isFallbackEnglishSummary,
  positionLabel,
  reportLevelLabel,
  scoreLabel,
  styleLabel,
  translatedValue,
} from "@/utils/display";

const route = useRoute();
const router = useRouter();
const detail = ref<HistoryInterviewDetail | null>(null);
const expandedQuestions = ref<string[]>([]);
let refreshTimer: number | null = null;
const REFRESH_INTERVAL_MS = 1500;

const competencyRows = computed(() =>
  Object.entries(detail.value?.competency_scores || {}).map(([competency, score]) => ({
    competency: competencyLabel(competency),
    score,
  })),
);

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "--";
}

function archiveSummary(current: HistoryInterviewDetail | null) {
  if (!current) return "";
  if (!current.report_ready) {
    return "AI 正在分析你的面试，综合评分和完整报告稍后会自动显示。";
  }
  if (current.summary && !isFallbackEnglishSummary(current.summary)) {
    return current.summary;
  }
  return `本场面试总分 ${formatScore(current.total_score)} 分，当前水平为“${reportLevelLabel(current.report_level)}”。`;
}

function timelineLabel(item: HistoryQuestionRecord) {
  return item.counts_toward_total ? `第 ${item.round_no} 题` : `第 ${item.round_no} 题 · 追问`;
}

function scoreRows(source: Record<string, number | string | null>) {
  return Object.entries(source || {})
    .filter(([label]) => label !== "status")
    .map(([label, value]) => ({
      label: scoreLabel(label),
      value: typeof value === "number" ? value.toFixed(2) : translatedValue(value),
    }));
}

function resolveAudioUrl(path: string) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${window.location.origin}${path}`;
}

function audioFeatureRows(item: HistoryQuestionRecord) {
  const features = item.audio_features as AudioFeatureSummary | null | undefined;
  if (!features || features.status !== "available") return [];
  return [
    { label: "停顿占比", value: formatMetric(features.pause_ratio) },
    { label: "语速", value: formatMetric(features.speech_rate) },
    { label: "有效发声占比", value: formatMetric(features.voiced_ratio) },
  ];
}

function normalizeAnswerText(value?: string | null) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function primaryAnswerText(item: HistoryQuestionRecord) {
  if (item.answer_mode === "audio") {
    return item.asr_text || item.answer_text || "AI 正在转写语音内容...";
  }
  return item.answer_text || "无回答记录";
}

function shouldShowTranscript(item: HistoryQuestionRecord) {
  if (item.answer_mode !== "audio" || !item.asr_text) return false;
  const primary = normalizeAnswerText(primaryAnswerText(item));
  const transcript = normalizeAnswerText(item.asr_text);
  return Boolean(transcript) && transcript !== primary;
}

function formatMetric(value?: number | null) {
  return typeof value === "number" ? value.toFixed(2) : "--";
}

function formatDuration(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return "--";
  if (value < 60) return `${Math.round(value)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes} 分 ${seconds} 秒`;
}

function showAudioSection(item: HistoryQuestionRecord) {
  return item.answer_mode === "audio" && (item.audio_scores?.status === "available" || item.audio_features?.status === "available");
}

async function handleDelete() {
  if (!detail.value) return;
  await ElMessageBox.confirm(`删除后将移除“${detail.value.title}”的完整面试档案，且无法恢复。`, "删除面试记录", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning",
  });
  await deleteHistory(detail.value.session_id);
  ElMessage.success("面试记录已删除");
  await router.push("/history");
}

async function loadDetail() {
  detail.value = (await fetchHistoryDetail(Number(route.params.id))).data;
  if (detail.value && !expandedQuestions.value.length && detail.value.questions.length) {
    expandedQuestions.value = [String(detail.value.questions[0].question_id)];
  }
  if (detail.value?.report_ready) {
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
  if (detail.value?.report_ready) return;
  refreshTimer = window.setTimeout(async () => {
    await loadDetail();
    scheduleRefresh();
  }, REFRESH_INTERVAL_MS);
}

onMounted(async () => {
  await loadDetail();
  scheduleRefresh();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.archive-hero,
.section-card {
  padding: 20px;
}

.archive-hero,
.header-row,
.question-header,
.block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.detail-grid,
.score-grid {
  display: grid;
  gap: 16px;
}

.detail-grid {
  grid-template-columns: 1fr 1fr;
}

.score-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.question-stack {
  margin-top: 16px;
}

.question-card,
.score-card {
  border-radius: 20px;
  border: 1px solid rgba(30, 60, 110, 0.08);
  background: rgba(255, 255, 255, 0.56);
}

.question-card {
  overflow: hidden;
  margin-bottom: 16px;
}

.score-card {
  padding: 14px;
}

.question-meta,
.score-card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.question-meta {
  flex-shrink: 0;
}

.score-pill {
  min-width: 72px;
  padding: 10px 12px;
  border-radius: 999px;
  background: rgba(90, 169, 255, 0.10);
  color: var(--primary);
  text-align: center;
  font-weight: 700;
}

.mode-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(90, 169, 255, 0.10);
  color: var(--primary-deep);
  font-size: 12px;
  font-weight: 600;
}

.content-panel {
  margin-top: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(30, 60, 110, 0.08);
}

.prompt-block {
  background: linear-gradient(135deg, rgba(90, 169, 255, 0.06), rgba(255, 255, 255, 0.92));
}

.answer-block {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06), rgba(255, 255, 255, 0.94));
}

.transcript-block,
.explanation-block {
  background: rgba(255, 255, 255, 0.84);
}

.feedback-block {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(255, 251, 235, 0.96));
  border-color: rgba(245, 158, 11, 0.14);
}

.block-label {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
}

.content-text {
  margin: 0;
  line-height: 1.8;
}

.block-meta,
.score-caption {
  color: var(--muted);
  font-size: 12px;
}

.preserve {
  white-space: pre-wrap;
}

.suggestion-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}

.muted {
  color: var(--muted);
}

.analysis-pending,
.pending-inline {
  background: rgba(90, 169, 255, 0.06);
}

.audio-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.metric-chip {
  padding: 12px;
  border-radius: 14px;
  background: rgba(90, 169, 255, 0.08);
}

.metric-chip span,
.metric-chip strong {
  display: block;
}

.metric-chip span {
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 12px;
}

.metric-chip strong {
  color: var(--text);
  font-size: 16px;
}

.audio-player {
  width: 100%;
  max-width: 420px;
  margin-top: 12px;
}

:deep(.question-stack .el-collapse) {
  border: 0;
}

:deep(.question-stack .el-collapse-item__header) {
  height: auto;
  padding: 18px;
  border: 0;
  background: transparent;
  line-height: 1.5;
}

:deep(.question-stack .el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}

:deep(.question-stack .el-collapse-item__content) {
  padding: 0 18px 18px;
}

@media (max-width: 960px) {
  .archive-hero,
  .header-row,
  .question-header,
  .block-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-actions {
    width: 100%;
    flex-direction: column;
  }

  .detail-grid,
  .score-grid {
    grid-template-columns: 1fr;
  }

  .question-meta,
  .score-card-head,
  .audio-metrics {
    width: 100%;
  }

  .audio-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
