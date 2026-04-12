<template>
  <div class="page-grid">
    <section class="panel-card create-card">
      <div class="header-row">
        <div class="heading-copy">
          <p class="eyebrow">面试设置</p>
          <h2>新建模拟面试</h2>
        </div>
      </div>

      <div v-if="activeInterview" class="active-session-card">
        <div>
          <p class="active-title">你有一场未完成的面试</p>
          <p class="active-copy">
            {{ activeInterview.position }} / 已进行第{{ activeInterview.current_turn || 1 }}题 / AI 动态控制 {{ activeInterview.min_questions }}-{{ activeInterview.max_questions }} 题
          </p>
          <p class="active-copy">
            开始于 {{ formatDateTime(activeInterview.created_at) }}，将于 {{ formatDateTime(activeInterview.expires_at) }} 自动过期。
          </p>
        </div>
        <div class="active-actions">
          <el-button @click="resumeActiveInterview">继续作答</el-button>
          <el-button type="danger" plain :loading="discarding" @click="discardActiveAndRefresh">删除</el-button>
        </div>
      </div>

      <div class="mode-selector">
        <div
          class="mode-card"
          :class="{ selected: interviewMode === 'normal' }"
          @click="interviewMode = 'normal'"
        >
          <div class="mode-icon">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="mode-info">
            <h3>普通面试</h3>
            <p>以文本问答为主，可配合当前能力逐步展开更贴近真实面试的追问。</p>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ selected: interviewMode === 'immersive', disabled: !immersiveModeReady }"
          @click="interviewMode = 'immersive'"
        >
          <div class="mode-icon accent">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z" stroke="currentColor" stroke-width="1.5"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="mode-info">
            <h3>沉浸式语音面试</h3>
            <p>问题会自动语音播报，页面会直接进入语音作答流程，体验更接近真实口语面试。</p>
          </div>
        </div>
      </div>

      <div class="setup-grid">
        <section class="panel-card nested-card config-card">
          <div class="section-head">
            <div>
              <h3>基础设置</h3>
            </div>
          </div>

          <el-form :model="form" label-position="top" class="form-grid">
            <el-form-item label="目标岗位">
              <el-select v-model="form.position_code" placeholder="请选择岗位">
                <el-option v-for="item in positionStore.items" :key="item.code" :label="positionLabel(item.name, item.code)" :value="item.code" />
              </el-select>
            </el-form-item>

            <el-form-item label="面试风格">
              <div class="difficulty-grid">
                <button
                  v-for="item in difficultyOptions"
                  :key="item.value"
                  type="button"
                  class="difficulty-card"
                  :class="{ selected: form.style === item.value }"
                  @click="form.style = item.value"
                >
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.audience }}</span>
                </button>
              </div>
            </el-form-item>
          </el-form>
        </section>

        <section class="panel-card nested-card resume-selector-card">
          <div class="selector-header">
            <div>
              <h3>面试简历</h3>
            </div>
            <div class="selector-actions">
              <el-button text :loading="libraryLoading" @click="refreshLibrary">刷新</el-button>
              <el-button type="primary" plain @click="goToResumeCenter">打开简历中心</el-button>
            </div>
          </div>

          <div class="resume-picker-row">
            <el-select
              :model-value="resume?.id ?? null"
              class="resume-picker"
              clearable
              filterable
              placeholder="从已上传简历中选择"
              :loading="libraryLoading"
              @change="handleResumeSelection"
              @clear="clearResumeSelection"
            >
              <el-option
                v-for="item in resumeLibrary"
                :key="item.id"
                :label="item.filename"
                :value="item.id"
              >
                <div class="option-row">
                  <span>{{ item.filename }}</span>
                  <span class="option-meta">{{ statusLabel(item.status) }} / {{ formatScore(item.summary?.overall_score) }}</span>
                </div>
              </el-option>
            </el-select>
          </div>

          <div v-if="resume" class="resume-summary-card">
            <div class="resume-summary-head">
              <div>
                <strong>{{ selectedResumeLabel }}</strong>
                <p class="muted">更新于 {{ formatDateTime(resume.updated_at) }}</p>
              </div>
              <div class="summary-actions">
                <el-tag :type="statusTagType(resume.status)" effect="plain">{{ statusLabel(resume.status) }}</el-tag>
                <span class="summary-chip">评分 {{ formatScore(resumeSummary?.overall_score) }}</span>
              </div>
            </div>

            <div class="resume-selection-note">
              <span class="meta-label">当前状态</span>
              <strong>{{ currentJobMatch ? `${currentJobMatch.position_name} / ${currentJobMatch.level}` : "已选择简历" }}</strong>
              <p class="muted">开始面试后，系统会在后台参考简历内容生成问题。</p>
            </div>
          </div>

          <div v-else class="empty-selection">
            <el-empty description="当前未选择简历" />
          </div>
        </section>
      </div>

      <div class="footer-row">
        <div class="resume-upload-tip">
          <strong>{{ resume ? `当前已选简历：${resume.filename}` : "当前未选择简历" }}</strong>
          <p class="muted">选中简历后，追问会优先围绕项目经历、岗位匹配和风险点展开，让面试更贴近真实场景。</p>
        </div>
        <el-button
          type="primary"
          size="large"
          :loading="starting"
          :disabled="!canStartInterview"
          @click="handleStart"
        >
          {{ interviewMode === 'immersive' ? "开始语音面试" : "开始面试" }}
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { discardInterview, fetchActiveInterview } from "@/api/interviews";
import { fetchInterviewCapabilities } from "@/api/system";
import { useInterviewFlow } from "@/composables/useInterviewFlow";
import { useResumeStore } from "@/stores/resume";
import { usePositionStore } from "@/stores/positions";
import type { ActiveInterview, InterviewCapabilities, ResumeJobMatch } from "@/types/models";
import { positionLabel, styleLabel } from "@/utils/display";

const route = useRoute();
const router = useRouter();
const positionStore = usePositionStore();
const resumeStore = useResumeStore();
const { startInterview } = useInterviewFlow();
const {
  library: resumeLibrary,
  libraryLoading,
  selectedResume: resume,
  selectedSummary: resumeSummary,
} = storeToRefs(resumeStore);

const starting = ref(false);
const discarding = ref(false);
const initialized = ref(false);
const capabilities = ref<InterviewCapabilities | null>(null);
const activeInterview = ref<ActiveInterview | null>(null);
const interviewMode = ref<"normal" | "immersive">("normal");
const difficultyOptions = [
  { value: "simple", label: "简单", audience: "适合校招、实习、基础摸底人群" },
  { value: "medium", label: "中等", audience: "适合常规社招、日常面试准备" },
  { value: "hard", label: "困难", audience: "适合高薪岗位、大厂、资深候选人" },
] as const;

const form = reactive({
  position_code: "cpp_backend",
  style: "medium",
});

const immersiveModeReady = computed(() =>
  Boolean(capabilities.value?.llm_ready) &&
  Boolean(capabilities.value?.embedding_ready) &&
  Boolean(capabilities.value?.immersive_voice_interview_ready),
);
const immersiveModeBlockedReason = computed(() => {
  if (!capabilities.value) {
    return "正在检查语音面试能力...";
  }
  if (!capabilities.value.llm_ready || !capabilities.value.embedding_ready || !capabilities.value.immersive_voice_interview_ready) {
    return "语音面试需要 LLM、Embedding、ASR 和 TTS 服务均已就绪。";
  }
  return "";
});
const canStartInterview = computed(() => Boolean(form.position_code) && (interviewMode.value !== "immersive" || immersiveModeReady.value));
const difficultyLabel = computed(() => styleLabel(form.style));
const difficultyAudience = computed(() => difficultyOptions.find((item) => item.value === form.style)?.audience || "");
const currentJobMatch = computed<ResumeJobMatch | null>(() => {
  if (!resumeSummary.value) return null;
  const match =
    resumeSummary.value.job_matches.find((item) => item.position_code === form.position_code) ||
    resumeSummary.value.best_job_match;
  if (!match) return null;
  return {
    ...match,
    position_name: positionLabel(match.position_name, match.position_code),
  };
});
const selectedResumeLabel = computed(() => {
  if (!resume.value) return "当前简历";
  return `${resume.value.filename}${resumeSummary.value?.candidate_name ? ` / ${resumeSummary.value.candidate_name}` : ""}`;
});
const routeResumeId = computed(() => parseResumeId(route.query.resumeId));

watch(
  () => route.query.resumeId,
  async () => {
    if (!initialized.value) return;
    await syncResumeSelectionFromRoute();
  },
);

onMounted(async () => {
  const [, capabilityResponse] = await Promise.all([
    positionStore.loadPositions(),
    fetchInterviewCapabilities(),
    refreshActiveInterview(),
    refreshLibrary(),
  ]);
  capabilities.value = capabilityResponse.data;
  initialized.value = true;
  await syncResumeSelectionFromRoute();
});

function parseResumeId(value: unknown) {
  const raw = Array.isArray(value) ? value[0] : value;
  if (typeof raw !== "string") return null;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "--";
}

function statusLabel(status: string) {
  if (status === "parsed") return "已分析";
  if (status === "failed") return "解析失败";
  return "待分析";
}

function statusTagType(status: string) {
  if (status === "parsed") return "success";
  if (status === "failed") return "danger";
  return "warning";
}

async function refreshActiveInterview() {
  const response = await fetchActiveInterview();
  activeInterview.value = response.data;
  return response.data;
}

async function refreshLibrary() {
  await resumeStore.loadLibrary();
}

async function syncResumeSelectionFromRoute() {
  if (!routeResumeId.value) return;
  try {
    await resumeStore.selectResumeById(routeResumeId.value, { fetchSummary: true });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载简历失败");
  }
}

async function handleResumeSelection(value: number | string | null) {
  if (!value) {
    clearResumeSelection();
    return;
  }
  try {
    await resumeStore.selectResumeById(Number(value), { fetchSummary: true });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "选择简历失败");
  }
}

function clearResumeSelection() {
  resumeStore.clearSelection();
}

function goToResumeCenter() {
  const query: Record<string, string> = {
    tab: resume.value ? "analysis" : resumeLibrary.value.length ? "history" : "upload",
  };
  if (resume.value) {
    query.resumeId = String(resume.value.id);
  }
  router.push({ path: "/resumes", query });
}

function resumeActiveInterview() {
  if (!activeInterview.value) return;
  router.push(`/interviews/${activeInterview.value.id}/run`);
}

async function discardActiveAndRefresh() {
  if (!activeInterview.value) return;
  try {
    await ElMessageBox.confirm(
      "删除后，这场未完成面试会被直接移除，且不会进入历史记录。",
      "删除未完成面试",
      {
        type: "warning",
        confirmButtonText: "确认删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  discarding.value = true;
  try {
    await discardInterview(activeInterview.value.id);
    activeInterview.value = null;
    ElMessage.success("未完成面试已删除");
    await refreshActiveInterview();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除未完成面试失败");
  } finally {
    discarding.value = false;
  }
}

async function handleStart() {
  if (interviewMode.value === "immersive" && !immersiveModeReady.value) {
    ElMessage.error(immersiveModeBlockedReason.value || "语音面试能力尚未就绪");
    return;
  }

  starting.value = true;
  try {
    const existing = await refreshActiveInterview();
    if (existing) {
      await resolveExistingInterview(existing);
      return;
    }
    await createNewInterview();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建面试失败");
    await refreshActiveInterview();
  } finally {
    starting.value = false;
  }
}

async function createNewInterview() {
  const session = await startInterview(
    {
      ...form,
      answer_mode: interviewMode.value === "immersive" ? "audio" : "text",
      resume_id: resume.value?.id || null,
    },
    resumeSummary.value,
  );
  router.push(`/interviews/${session.id}/run`);
}

async function resolveExistingInterview(existing: ActiveInterview) {
  try {
    await ElMessageBox.confirm(
      "当前已有一场未完成面试。你可以继续作答，或删除后重新开始新的面试。",
      "发现未完成面试",
      {
        type: "warning",
        confirmButtonText: "继续作答",
        cancelButtonText: "删除并重开",
        distinguishCancelAndClose: true,
        closeOnClickModal: false,
        closeOnPressEscape: false,
      },
    );
    router.push(`/interviews/${existing.id}/run`);
  } catch (action) {
    if (action !== "cancel") {
      return;
    }
    await discardInterview(existing.id);
    activeInterview.value = null;
    ElMessage.success("原未完成面试已删除");
    await createNewInterview();
  }
}
</script>

<style scoped>
.create-card {
  padding: 24px;
}

.header-row,
.selector-header,
.footer-row,
.resume-summary-head,
.summary-actions,
.active-actions,
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.heading-copy {
  max-width: 760px;
}

.heading-copy .muted {
  margin: 8px 0 0;
}

.header-summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.summary-badge {
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

.summary-badge.warm {
  background: rgba(201, 111, 61, 0.12);
  color: var(--accent);
}

.active-session-card {
  margin: 20px 0 6px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(201, 111, 61, 0.2);
  background: linear-gradient(135deg, rgba(245, 216, 194, 0.58), rgba(255, 255, 255, 0.76));
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.active-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
}

.active-copy {
  margin: 4px 0 0;
  color: var(--muted);
}

.mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 22px 0;
}

.mode-card {
  display: flex;
  gap: 16px;
  padding: 22px;
  border-radius: 22px;
  border: 1px solid rgba(64, 46, 30, 0.1);
  background: rgba(255, 255, 255, 0.62);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.mode-card:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.18);
  box-shadow: var(--shadow-soft);
}

.mode-card.selected {
  border-color: rgba(15, 118, 110, 0.24);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.1), rgba(255, 255, 255, 0.82));
}

.mode-card.disabled {
  opacity: 0.72;
}

.mode-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--primary-soft);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.mode-icon.accent {
  background: rgba(201, 111, 61, 0.14);
  color: var(--accent);
}

.mode-info h3 {
  margin: 0 0 8px;
  font-size: 17px;
}

.mode-info p,
.helper-text,
.muted {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.setup-grid {
  display: grid;
  grid-template-columns: 0.92fr 1.08fr;
  gap: 16px;
}

.nested-card {
  padding: 20px;
  background: rgba(255, 255, 255, 0.54);
}

.config-card,
.resume-selector-card {
  display: grid;
  gap: 18px;
}

.section-head h3,
.selector-header h3 {
  margin-bottom: 6px;
}

.form-grid {
  display: grid;
  gap: 4px;
}

.difficulty-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.difficulty-card {
  border: 1px solid rgba(64, 46, 30, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 6px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.difficulty-card strong {
  color: var(--primary);
  font-size: 15px;
}

.difficulty-card span {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}

.difficulty-card:hover {
  transform: translateY(-1px);
  border-color: rgba(15, 118, 110, 0.18);
}

.difficulty-card.selected {
  border-color: rgba(15, 118, 110, 0.28);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(255, 255, 255, 0.88));
  box-shadow: var(--shadow-soft);
}

.resume-picker-row {
  display: grid;
  gap: 10px;
}

.resume-picker {
  width: 100%;
}

.selector-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.option-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.option-meta {
  color: var(--muted);
  font-size: 12px;
}

.resume-summary-card,
.resume-selection-note {
  border: 1px solid rgba(64, 46, 30, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.8);
}

.resume-summary-card {
  padding: 18px;
}

.summary-actions {
  align-items: center;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  color: var(--primary);
  font-weight: 700;
}

.resume-selection-note {
  margin-top: 16px;
  padding: 14px 16px;
}

.resume-selection-note strong {
  color: var(--primary);
  line-height: 1.6;
}

.meta-label {
  display: block;
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 8px;
}

.empty-selection {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resume-upload-tip {
  flex: 1;
}

@media (max-width: 1100px) {
  .setup-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .mode-selector,
  .difficulty-grid {
    grid-template-columns: 1fr;
  }

  .header-row,
  .selector-header,
  .section-head,
  .active-session-card,
  .footer-row,
  .resume-summary-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-summary,
  .selector-actions,
  .active-actions,
  .summary-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
