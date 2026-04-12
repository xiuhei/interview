<template>
  <div class="panel-card sidebar-card">
    <h3>单题反馈</h3>
    <template v-if="evaluation">
      <el-progress :percentage="evaluation.overall_score" :stroke-width="14" />
      <p class="summary">{{ evaluation.explanation }}</p>

      <div class="score-grid">
        <div class="score-block">
          <strong>文本维度</strong>
          <ul>
            <li v-for="item in textScoreRows" :key="item.label">{{ item.label }}：{{ item.value }}</li>
          </ul>
        </div>
        <div v-if="audioScoreRows.length" class="score-block">
          <strong>语音维度</strong>
          <ul>
            <li v-for="item in audioScoreRows" :key="item.label">{{ item.label }}：{{ item.value }}</li>
          </ul>
        </div>
      </div>

      <div class="list-block">
        <strong>建议优化</strong>
        <ul>
          <li v-for="item in evaluation.suggestions" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div v-if="showEvidence" class="list-block">
        <strong>评分依据</strong>
        <ul>
          <li v-for="item in evaluation.evidence" :key="item.doc_id">{{ item.title }}：{{ item.snippet }}</li>
        </ul>
      </div>
    </template>
    <template v-else-if="loading">
      <el-empty description="下一题已生成，当前题评分正在后台整理中" />
    </template>
    <el-empty v-else description="提交答案后显示评分与追问依据" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { AnswerEvaluation } from "@/types/models";

const props = defineProps<{
  evaluation: AnswerEvaluation | null;
  loading?: boolean;
  showEvidence?: boolean;
}>();

const TEXT_SCORE_LABELS: Record<string, string> = {
  accuracy: "准确性",
  completeness: "完整度",
  logic: "逻辑性",
  job_fit: "岗位匹配度",
  credibility: "可信度",
};

const showEvidence = computed(() => props.showEvidence ?? false);

const AUDIO_SCORE_LABELS: Record<string, string> = {
  confidence: "语音自信度",
  clarity: "语音清晰度",
  fluency: "语音流畅度",
  emotion: "情绪稳定度",
  speech_rate_comment: "语速评价",
  pause_comment: "停顿评价",
};

function formatValue(value: string | number | null | undefined) {
  if (typeof value === "number") {
    return value.toFixed(1);
  }
  return value ?? "--";
}

const textScoreRows = computed(() =>
  Object.entries(props.evaluation?.text_scores || {}).map(([key, value]) => ({
    label: TEXT_SCORE_LABELS[key] || key,
    value: formatValue(value),
  })),
);

const audioScoreRows = computed(() => {
  const audioScores = props.evaluation?.audio_scores || {};
  if (audioScores.status !== "available") {
    return [];
  }
  return Object.entries(audioScores)
    .filter(([key]) => key !== "status")
    .map(([key, value]) => ({
      label: AUDIO_SCORE_LABELS[key] || key,
      value: formatValue(value),
    }));
});
</script>

<style scoped>
.sidebar-card {
  padding: 18px;
}

.summary {
  color: var(--muted);
  line-height: 1.7;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.score-block {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid var(--border);
}

.list-block ul,
.score-block ul {
  padding-left: 18px;
  color: var(--muted);
}

@media (max-width: 960px) {
  .score-grid {
    grid-template-columns: 1fr;
  }
}
</style>
