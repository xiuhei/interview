<template>
  <div class="page-grid">
    <section class="hero panel-card">
      <div class="hero-copy">
        <h2>欢迎回来，{{ auth.user?.full_name }}</h2>
      </div>

      <div class="hero-actions">
        <el-button plain @click="router.push('/resumes')">打开简历中心</el-button>
        <el-button type="primary" size="large" @click="router.push('/interviews/new')">开始新面试</el-button>
      </div>
    </section>

    <section class="metrics">
      <MetricCard label="可选岗位" :value="positions.length" hint="当前支持 C++ 后端开发和 Web 前端开发" />
      <MetricCard label="完成场次" :value="history.length" hint="只有已完成的面试会进入历史与成长分析" />
      <MetricCard label="当前均分" :value="averageScore" hint="基于已完成场次自动计算" />
      <MetricCard label="当前水平" :value="insight?.summary.readiness_label || '待开始'" hint="根据已完成面试的整体表现生成" />
    </section>

    <section class="content-grid">
      <div class="panel-card block">
        <div class="header-row">
          <div>
            <h3>最近面试记录</h3>
            <p class="muted section-copy">快速回看最近完成的面试和评分结果。</p>
          </div>
          <el-button link @click="router.push('/history')">查看全部</el-button>
        </div>

        <div class="table-shell">
          <el-table :data="history.slice(0, 5)">
            <el-table-column prop="title" label="标题" />
            <el-table-column label="岗位">
              <template #default="scope">
                {{ positionLabel(scope.row.position) }}
              </template>
            </el-table-column>
            <el-table-column label="状态">
              <template #default="scope">
                {{ interviewStatusLabel(scope.row.status) }}
              </template>
            </el-table-column>
            <el-table-column label="分数">
              <template #default="scope">
                {{ formatHistoryScore(scope.row.total_score, scope.row.report_ready) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="panel-card block focus-card">
        <div class="header-row compact">
          <div>
            <h3>本阶段训练重点</h3>
            <p class="muted section-copy">根据历史面试自动提炼的优势与短板。</p>
          </div>
          <span class="focus-chip">{{ competencyLabel(insight?.summary.focus_competency) }}</span>
        </div>

        <p class="focus-copy">{{ insight?.summary.narrative || emptyNarrative }}</p>

        <div class="focus-grid">
          <div class="focus-stat">
            <span class="focus-label">优势能力</span>
            <strong>{{ competencyLabel(insight?.summary.strongest_competency, "暂无") }}</strong>
          </div>
          <div class="focus-stat warm">
            <span class="focus-label">重点补强</span>
            <strong>{{ competencyLabel(insight?.summary.focus_competency) }}</strong>
          </div>
        </div>

        <ol class="plan-list">
          <li v-for="item in (insight?.plan || []).slice(0, 3)" :key="item.title">
            <strong>{{ item.title }}</strong>
            <p>{{ item.action }}</p>
          </li>
        </ol>
      </div>
    </section>

    <GrowthInsightPanel :insight="insight" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import GrowthInsightPanel from "@/components/GrowthInsightPanel.vue";
import MetricCard from "@/components/MetricCard.vue";
import { fetchGrowthInsight } from "@/api/growth";
import { fetchHistory } from "@/api/interviews";
import { useAuthStore } from "@/stores/auth";
import { usePositionStore } from "@/stores/positions";
import type { GrowthInsight, HistoryItem } from "@/types/models";
import { competencyLabel as formatCompetencyLabel, interviewStatusLabel, positionLabel } from "@/utils/display";

const emptyNarrative = "完成第一场面试后，这里会自动总结你的能力优势、短板和提升建议。";
const router = useRouter();
const auth = useAuthStore();
const positionStore = usePositionStore();
const history = ref<HistoryItem[]>([]);
const insight = ref<GrowthInsight | null>(null);

const positions = computed(() => positionStore.items);
const averageScore = computed(() => {
  const value = insight.value?.summary.average_score;
  return typeof value === "number" ? value.toFixed(1) : "--";
});

function competencyLabel(value?: string | null, fallback = "综合能力") {
  if (!value) return fallback;
  return formatCompetencyLabel(value);
}

function formatHistoryScore(value?: number | null, reportReady?: boolean) {
  if (!reportReady || typeof value !== "number") return "分析中";
  return value.toFixed(1);
}

onMounted(async () => {
  await positionStore.loadPositions();
  const [historyResponse, growthResponse] = await Promise.all([
    fetchHistory(),
    fetchGrowthInsight(),
  ]);
  history.value = historyResponse.data;
  insight.value = growthResponse.data;
});
</script>

<style scoped>
.hero,
.block {
  padding: 24px;
}

.hero,
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.hero {
  background:
    radial-gradient(circle at top right, rgba(90, 169, 255, 0.08), transparent 24%),
    linear-gradient(135deg, rgba(248, 252, 255, 0.96), rgba(235, 244, 255, 0.76));
}

.hero-copy {
  max-width: 720px;
}

.hero-copy h2 {
  margin-bottom: 10px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.focus-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(30, 60, 110, 0.08);
  color: var(--muted-strong);
  font-size: 13px;
  font-weight: 600;
  background: rgba(90, 169, 255, 0.08);
  color: var(--primary);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 16px;
}

.section-copy {
  margin: 6px 0 0;
}

.compact {
  align-items: center;
}

.table-shell {
  margin-top: 18px;
  padding: 8px 14px 0;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(30, 60, 110, 0.08);
}

.focus-card {
  display: grid;
  gap: 18px;
}

.focus-copy {
  margin: 0;
  color: var(--muted);
  line-height: 1.8;
}

.focus-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.focus-stat {
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(30, 60, 110, 0.08);
}

.focus-stat.warm {
  background: linear-gradient(135deg, rgba(90, 169, 255, 0.10), rgba(255, 255, 255, 0.8));
}

.focus-stat strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
}

.focus-label {
  color: var(--muted);
  font-size: 12px;
}

.plan-list {
  margin: 0;
  padding-left: 18px;
}

.plan-list p {
  margin: 6px 0 12px;
  color: var(--muted);
}

@media (max-width: 1100px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .hero,
  .header-row {
    flex-direction: column;
  }

  .hero-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .metrics,
  .focus-grid {
    grid-template-columns: 1fr;
  }
}
</style>
