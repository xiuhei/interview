<template>
  <div class="page-grid">
    <section class="hero panel-card">
      <div class="hero-copy">
        <p class="eyebrow">训练洞察</p>
        <h2>个人成长</h2>
        <p class="muted">这里集中展示你在已完成面试中的趋势变化、能力强弱项，以及下一步更适合投入的训练方向。</p>
      </div>

      <div class="hero-actions">
        <el-button plain @click="router.push('/history')">查看历史记录</el-button>
        <el-button type="primary" size="large" @click="router.push('/interviews/new')">开始新面试</el-button>
      </div>
    </section>

    <section class="focus-grid">
      <div class="panel-card focus-card">
        <p class="focus-label">当前水平</p>
        <strong>{{ insight?.summary.readiness_label || "待开始" }}</strong>
        <p class="muted">{{ insight?.summary.narrative || emptyNarrative }}</p>
      </div>

      <div class="panel-card focus-card warm">
        <p class="focus-label">下一步训练重点</p>
        <strong>{{ competencyLabel(insight?.summary.focus_competency) }}</strong>
        <p class="muted">
          {{ firstPlan?.action || "完成一轮面试后，这里会自动生成专项训练建议。" }}
        </p>
      </div>
    </section>

    <GrowthInsightPanel :insight="insight" />

    <section class="detail-grid">
      <div class="panel-card block">
        <div class="header-row">
          <div>
            <h3>专项训练建议</h3>
            <p class="muted section-copy">按能力短板拆分的练习方向与行动建议。</p>
          </div>
          <span class="summary-pill">{{ (insight?.plan || []).length }} 条建议</span>
        </div>

        <div v-if="insight?.plan?.length" class="plan-stack">
          <article v-for="item in insight.plan" :key="item.title" class="plan-card">
            <h4>{{ item.title }}</h4>
            <p><strong>聚焦：</strong>{{ item.focus }}</p>
            <p><strong>行动：</strong>{{ item.action }}</p>
            <p><strong>预期结果：</strong>{{ item.expected_result }}</p>
          </article>
        </div>
        <p v-else class="muted">完成第一场面试后，这里会生成更具体的专项训练计划。</p>
      </div>

      <div class="panel-card block">
        <div class="header-row">
          <div>
            <h3>近期薄弱点</h3>
            <p class="muted section-copy">仅统计已完成面试，方便你快速聚焦高频问题。</p>
          </div>
          <span class="summary-pill warm">趋势观察</span>
        </div>

        <div v-if="insight?.weaknesses?.length" class="weakness-list">
          <div v-for="item in insight.weaknesses" :key="item.tag" class="weakness-card">
            <strong>{{ competencyLabel(item.tag, item.tag) }}</strong>
            <p>出现次数：{{ item.count }}</p>
            <p>平均分：{{ item.avg_score.toFixed(1) }}</p>
          </div>
        </div>
        <p v-else class="muted">当前还没有可统计的薄弱项，继续完成几场面试后会更准确。</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import GrowthInsightPanel from "@/components/GrowthInsightPanel.vue";
import { fetchGrowthInsight } from "@/api/growth";
import type { GrowthInsight, GrowthPlanItem } from "@/types/models";
import { competencyLabel as formatCompetencyLabel } from "@/utils/display";

const router = useRouter();
const insight = ref<GrowthInsight | null>(null);
const emptyNarrative = "完成第一场面试后，这里会自动整理你的能力趋势、优势项和后续训练重点。";

const firstPlan = computed<GrowthPlanItem | null>(() => insight.value?.plan?.[0] || null);

function competencyLabel(value?: string | null, fallback = "综合能力") {
  if (!value) return fallback;
  return formatCompetencyLabel(value);
}

onMounted(async () => {
  const response = await fetchGrowthInsight();
  insight.value = response.data;
});
</script>

<style scoped>
.hero,
.block,
.focus-card {
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
    radial-gradient(circle at top right, rgba(201, 111, 61, 0.1), transparent 24%),
    linear-gradient(135deg, rgba(255, 252, 248, 0.96), rgba(242, 236, 228, 0.78));
}

.hero-copy {
  max-width: 720px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.focus-grid,
.detail-grid {
  display: grid;
  gap: 16px;
}

.focus-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-grid {
  grid-template-columns: 1.1fr 0.9fr;
}

.focus-card {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.82), rgba(244, 239, 230, 0.62));
}

.focus-card.warm {
  background:
    linear-gradient(135deg, rgba(201, 111, 61, 0.1), rgba(255, 255, 255, 0.82));
}

.focus-card strong {
  display: block;
  margin: 8px 0 10px;
  font-size: 24px;
}

.focus-label {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.section-copy {
  margin: 6px 0 0;
}

.summary-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
}

.summary-pill.warm {
  background: rgba(201, 111, 61, 0.12);
  color: var(--accent);
}

.plan-stack,
.weakness-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.plan-card,
.weakness-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(64, 46, 30, 0.08);
}

.plan-card h4,
.weakness-card strong {
  margin: 0 0 8px;
}

.plan-card p,
.weakness-card p {
  margin: 6px 0 0;
  color: var(--muted);
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .hero,
  .header-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .focus-grid {
    grid-template-columns: 1fr;
  }
}
</style>
