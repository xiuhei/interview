<template>
  <div class="page-grid">
    <section class="panel-card history-card">
      <div class="header-row">
        <div>
          <p class="eyebrow">面试档案</p>
          <h2>历史面试记录</h2>
          <p class="muted">这里展示所有已完成面试。你可以查看完整问答、转写结果和评分进度。</p>
        </div>

        <div class="header-actions">
          <el-button plain @click="router.push('/growth')">查看成长分析</el-button>
          <el-button type="primary" @click="router.push('/interviews/new')">开始新面试</el-button>
        </div>
      </div>

      <div class="summary-strip">
        <div class="summary-card">
          <span>总档案数</span>
          <strong>{{ history.length }}</strong>
        </div>
        <div class="summary-card">
          <span>已出报告</span>
          <strong>{{ history.filter((item) => item.report_ready).length }}</strong>
        </div>
        <div class="summary-card warm">
          <span>分析处理中</span>
          <strong>{{ history.filter((item) => !item.report_ready).length }}</strong>
        </div>
      </div>

      <div class="table-shell">
        <el-table :data="history">
          <el-table-column prop="title" label="标题" min-width="220" />
          <el-table-column label="岗位" width="180">
            <template #default="scope">
              {{ positionLabel(scope.row.position) }}
            </template>
          </el-table-column>
          <el-table-column label="面试类型" width="140">
            <template #default="scope">
              {{ styleLabel(scope.row.style) }}
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="完成时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.completed_at) }}
            </template>
          </el-table-column>
          <el-table-column label="总分" width="120">
            <template #default="scope">
              {{ formatHistoryScore(scope.row.total_score, scope.row.report_ready) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="scope">
              <el-button link @click="router.push(`/history/${scope.row.session_id}`)">查看档案</el-button>
              <el-button link type="danger" @click="handleDelete(scope.row)">删除记录</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { deleteHistory, fetchHistory } from "@/api/interviews";
import type { HistoryItem } from "@/types/models";
import { positionLabel, styleLabel } from "@/utils/display";

const router = useRouter();
const history = ref<HistoryItem[]>([]);
let refreshTimer: number | null = null;
const REFRESH_INTERVAL_MS = 3000;

async function loadHistory() {
  history.value = (await fetchHistory()).data;
}

function stopPolling() {
  if (refreshTimer !== null) {
    window.clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

function scheduleRefresh() {
  stopPolling();
  if (!history.value.some((item) => !item.report_ready)) return;
  refreshTimer = window.setTimeout(async () => {
    await loadHistory();
    scheduleRefresh();
  }, REFRESH_INTERVAL_MS);
}

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

function formatHistoryScore(value?: number | null, reportReady?: boolean) {
  if (!reportReady || typeof value !== "number") return "分析中";
  return value.toFixed(1);
}

async function handleDelete(row: HistoryItem) {
  await ElMessageBox.confirm(`删除后将移除“${row.title}”的完整面试档案，且无法恢复。`, "删除面试记录", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning",
  });
  await deleteHistory(row.session_id);
  ElMessage.success("面试记录已删除");
  await loadHistory();
  scheduleRefresh();
}

onMounted(async () => {
  await loadHistory();
  scheduleRefresh();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.history-card {
  padding: 24px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.summary-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(64, 46, 30, 0.08);
}

.summary-card.warm {
  background: linear-gradient(135deg, rgba(201, 111, 61, 0.12), rgba(255, 255, 255, 0.82));
}

.summary-card span {
  color: var(--muted);
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--ink-soft);
}

.table-shell {
  margin-top: 18px;
  padding: 8px 14px 0;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(64, 46, 30, 0.08);
}

@media (max-width: 900px) {
  .header-row {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .summary-strip {
    grid-template-columns: 1fr;
  }
}
</style>
