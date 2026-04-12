<template>
  <div class="page-grid">
    <section class="panel-card resume-center-card">
      <div class="header-row">
        <div class="heading-copy">
          <p class="eyebrow">简历中心</p>
          <h2>简历中心</h2>
        </div>

        <div class="header-actions">
          <el-button text :loading="libraryLoading" @click="refreshLibrary">刷新</el-button>
          <el-button type="primary" plain :disabled="!resume" @click="goToInterviewWithSelected">
            用于新建面试
          </el-button>
        </div>
      </div>

      <div class="summary-strip">
        <div class="summary-card">
          <span>简历总数</span>
          <strong>{{ library.length }}</strong>
        </div>
        <div class="summary-card">
          <span>已完成分析</span>
          <strong>{{ parsedCount }}</strong>
        </div>
        <div class="summary-card warm">
          <span>当前选择</span>
          <strong>{{ resume?.filename || "尚未选择" }}</strong>
        </div>
      </div>

      <el-tabs :model-value="activeTab" class="resume-tabs" @update:model-value="handleTabChange">
        <el-tab-pane label="提交简历" name="upload">
          <div class="tab-panel">
            <section class="panel-card nested-card upload-panel">
              <div class="upload-copy">
                <h3>上传后自动完成分析</h3>
              </div>

              <input
                ref="fileInputRef"
                :key="uploadInputKey"
                type="file"
                accept=".pdf,.docx,.txt,.md,.rtf"
                class="hidden-file-input"
                @change="onResumeChange"
              />

              <button
                type="button"
                class="upload-dropzone"
                :class="{ filled: Boolean(selectedFile), busy: uploading || parsing }"
                @click="openFileDialog"
              >
                <div class="upload-icon">
                  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
                    <path d="M12 16V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <path d="m7 9 5-5 5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M4 18.5A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </div>
                <div class="dropzone-copy">
                  <strong>{{ selectedFile ? "已选择简历文件" : "点击选择简历文件" }}</strong>
                  <p v-if="selectedFile" class="muted">{{ selectedFile.name }}</p>
                </div>
                <span class="dropzone-pill">{{ selectedFile ? "重新选择" : "选择文件" }}</span>
              </button>

              <div class="format-row">
                <span v-for="format in acceptedFormats" :key="format" class="format-chip">{{ format }}</span>
              </div>

              <div v-if="selectedFile" class="selected-file-card">
                <div>
                  <strong>{{ selectedFile.name }}</strong>
                  <p class="muted">文件大小 {{ formatFileSize(selectedFile.size) }}，上传后会自动解析并切换到分析页。</p>
                </div>
                <el-button text @click="clearSelectedFile">移除</el-button>
              </div>

              <div class="upload-actions">
                <div class="action-buttons">
                  <el-button @click="openFileDialog">浏览文件</el-button>
                  <el-button type="primary" :loading="uploading || parsing" @click="handleUpload">上传并分析</el-button>
                </div>
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="简历分析" name="analysis">
          <div v-if="resume && resumeSummary" class="analysis-stack">
            <section class="panel-card nested-card summary-hero">
              <div>
                <p class="eyebrow">分析结果</p>
                <h3>{{ selectedResumeLabel }}</h3>
                <p class="muted">
                  更新于 {{ formatDateTime(resume.updated_at) }}
                  <span v-if="resumeSummary.years_of_experience"> / {{ resumeSummary.years_of_experience }} 年经验</span>
                </p>
              </div>

              <div class="hero-side">
                <el-tag :type="statusTagType(resume.status)" effect="plain">{{ statusLabel(resume.status) }}</el-tag>
                <div class="summary-pill">
                  <strong>{{ formatScore(resumeSummary.overall_score) }}</strong>
                  <span>综合评分</span>
                </div>
              </div>
            </section>

            <section class="score-grid">
              <article class="score-card">
                <span>清晰度</span>
                <strong>{{ formatScore(resumeSummary.score_breakdown.clarity) }}</strong>
              </article>
              <article class="score-card">
                <span>项目深度</span>
                <strong>{{ formatScore(resumeSummary.score_breakdown.project_depth) }}</strong>
              </article>
              <article class="score-card">
                <span>结果表达</span>
                <strong>{{ formatScore(resumeSummary.score_breakdown.impact) }}</strong>
              </article>
              <article class="score-card">
                <span>岗位相关性</span>
                <strong>{{ formatScore(resumeSummary.score_breakdown.role_relevance) }}</strong>
              </article>
              <article class="score-card">
                <span>可信度</span>
                <strong>{{ formatScore(resumeSummary.score_breakdown.credibility) }}</strong>
              </article>
            </section>

            <section v-if="resumeSummary.job_matches.length" class="match-grid">
              <article
                v-for="match in resumeSummary.job_matches"
                :key="`${resume.id}-${match.position_code}`"
                class="panel-card nested-card match-card"
                :class="{ featured: bestJobMatch?.position_code === match.position_code }"
              >
                <div class="match-head">
                  <div>
                    <h4>{{ positionLabel(match.position_name, match.position_code) }}</h4>
                    <p class="muted">{{ match.level }}</p>
                  </div>
                  <strong class="match-score">{{ formatScore(match.score) }}</strong>
                </div>
                <p class="match-summary">{{ match.summary }}</p>
                <p class="match-detail"><strong>命中技能：</strong>{{ joinList(match.matched_skills, "待补充") }}</p>
                <p class="match-detail"><strong>缺口技能：</strong>{{ joinList(match.missing_skills, "暂无明显缺口") }}</p>
                <p class="match-detail"><strong>面试重点：</strong>{{ joinList(match.interview_focuses, "优先围绕代表项目展开") }}</p>
              </article>
            </section>

            <section class="analysis-columns">
              <article class="panel-card nested-card detail-card">
                <h3>背景概览</h3>
                <p class="detail-copy">{{ resumeSummary.background }}</p>

                <div class="field-block">
                  <h4>项目经历</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.project_experiences" :key="item" class="token">{{ item }}</span>
                  </div>
                </div>

                <div class="field-block">
                  <h4>技术栈</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.tech_stack" :key="item" class="token">{{ item }}</span>
                    <span v-if="!resumeSummary.tech_stack.length" class="token muted-token">暂未识别到技术栈</span>
                  </div>
                </div>
              </article>

              <article class="panel-card nested-card detail-card">
                <h3>亮点与建议</h3>

                <div class="field-block">
                  <h4>亮点</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.highlights" :key="item" class="token success-token">{{ item }}</span>
                  </div>
                </div>

                <div class="field-block">
                  <h4>风险点</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.risk_points" :key="item" class="token warning-token">{{ item }}</span>
                  </div>
                </div>

                <div class="field-block">
                  <h4>简历建议</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.resume_suggestions" :key="item" class="token">{{ item }}</span>
                  </div>
                </div>

                <div class="field-block">
                  <h4>优先追问</h4>
                  <div class="token-list">
                    <span v-for="item in resumeSummary.interview_focuses" :key="item" class="token accent-token">{{ item }}</span>
                  </div>
                </div>
              </article>
            </section>

            <div class="footer-row">
              <div class="resume-note">
                <strong>这份简历已经可以直接用于面试</strong>
                <p class="muted">后续追问会优先结合项目经历、风险点和岗位缺口展开。</p>
              </div>
              <el-button type="primary" size="large" @click="goToInterviewWithSelected">用于新建面试</el-button>
            </div>
          </div>

          <section v-else class="panel-card nested-card empty-card">
            <el-empty description="暂无可展示的分析结果">
              <template #description>
                <p class="muted">{{ analysisEmptyMessage }}</p>
              </template>
              <div class="empty-actions">
                <el-button v-if="library.length" @click="goToHistoryTab">从历史记录选择</el-button>
                <el-button type="primary" plain @click="goToUploadTab">去上传简历</el-button>
              </div>
            </el-empty>
          </section>
        </el-tab-pane>

        <el-tab-pane label="历史记录" name="history">
          <div v-if="library.length" class="history-grid">
            <article
              v-for="item in library"
              :key="item.id"
              class="panel-card nested-card history-card"
              :class="{ selected: resume?.id === item.id }"
            >
              <div class="history-head">
                <div>
                  <h3>{{ item.filename }}</h3>
                  <p class="muted">更新于 {{ formatDateTime(item.updated_at) }}</p>
                </div>
                <el-tag :type="statusTagType(item.status)" effect="plain">{{ statusLabel(item.status) }}</el-tag>
              </div>

              <div class="history-stats">
                <div class="history-stat">
                  <span>综合评分</span>
                  <strong>{{ formatScore(item.summary?.overall_score) }}</strong>
                </div>
                <div class="history-stat">
                  <span>最佳岗位匹配</span>
                  <strong>{{ bestMatchLabel(item) }}</strong>
                </div>
              </div>

              <p class="history-summary">{{ bestMatchSummary(item) }}</p>

              <div class="record-actions">
                <el-button :loading="parsing && resume?.id === item.id" @click="openAnalysis(item)">查看分析</el-button>
                <el-button type="primary" plain @click="useForInterview(item)">用于面试</el-button>
              </div>
            </article>
          </div>

          <section v-else class="panel-card nested-card empty-card">
            <el-empty description="还没有历史简历">
              <template #description>
                <p class="muted">先上传一份简历，之后就可以在这里快速复用。</p>
              </template>
              <el-button type="primary" plain @click="goToUploadTab">去上传简历</el-button>
            </el-empty>
          </section>
        </el-tab-pane>
      </el-tabs>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { useResumeStore } from "@/stores/resume";
import type { ResumeLibraryItem } from "@/types/models";
import { positionLabel } from "@/utils/display";

const TAB_VALUES = ["upload", "analysis", "history"] as const;
type ResumeTab = (typeof TAB_VALUES)[number];

const route = useRoute();
const router = useRouter();
const resumeStore = useResumeStore();
const {
  library,
  libraryLoading,
  loading: uploading,
  parsing,
  selectedResume: resume,
  selectedSummary: resumeSummary,
} = storeToRefs(resumeStore);

const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const uploadInputKey = ref(0);
const initialized = ref(false);
const acceptedFormats = ["PDF", "DOCX", "TXT", "MD", "RTF"];

const defaultTab = computed<ResumeTab>(() => (library.value.length ? "history" : "upload"));
const activeTab = computed<ResumeTab>(() => parseTab(route.query.tab) ?? defaultTab.value);
const routeResumeId = computed(() => parseResumeId(route.query.resumeId));
const bestJobMatch = computed(() => resumeSummary.value?.best_job_match || resumeSummary.value?.job_matches[0] || null);
const parsedCount = computed(() => library.value.filter((item) => item.status === "parsed").length);
const selectedResumeLabel = computed(() => {
  if (!resume.value) return "当前未选择简历";
  return `${resume.value.filename}${resumeSummary.value?.candidate_name ? ` / ${resumeSummary.value.candidate_name}` : ""}`;
});
const analysisEmptyMessage = computed(() => {
  if (library.value.length) {
    return "你可以从历史记录中选择简历，或先上传新的简历后查看分析。";
  }
  return "请先上传一份简历，我们会自动生成分析结果。";
});

onMounted(async () => {
  await resumeStore.loadLibrary();
  initialized.value = true;
  const routeReady = await ensureRouteState();
  if (routeReady) {
    await syncSelectionFromRoute();
  }
});

watch(
  () => [route.query.tab, route.query.resumeId],
  async () => {
    if (!initialized.value) return;
    const routeReady = await ensureRouteState();
    if (routeReady) {
      await syncSelectionFromRoute();
    }
  },
);

function normalizeQueryValue(value: unknown) {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return typeof value === "string" ? value : null;
}

function parseTab(value: unknown): ResumeTab | null {
  const raw = normalizeQueryValue(value);
  if (!raw || !TAB_VALUES.includes(raw as ResumeTab)) return null;
  return raw as ResumeTab;
}

function parseResumeId(value: unknown) {
  const raw = normalizeQueryValue(value);
  if (!raw) return null;
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

function formatFileSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
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

function joinList(items: string[], fallback: string) {
  return items.length ? items.join(" / ") : fallback;
}

function bestMatchLabel(item: ResumeLibraryItem) {
  if (!item.summary?.best_job_match) {
    return item.status === "parsed" ? "暂无明确匹配" : "待分析";
  }
  return `${positionLabel(item.summary.best_job_match.position_name, item.summary.best_job_match.position_code)} / ${item.summary.best_job_match.level}`;
}

function bestMatchSummary(item: ResumeLibraryItem) {
  if (item.summary?.best_job_match?.summary) {
    return item.summary.best_job_match.summary;
  }
  if (item.status === "failed") {
    return "上一次解析失败，点击“查看分析”会重新尝试解析。";
  }
  if (item.status === "parsed") {
    return "这份简历已完成分析，但暂时没有明显的岗位匹配结论。";
  }
  return "这份简历还没有完成分析，打开分析时会先自动解析。";
}

function resetSelectedFile() {
  selectedFile.value = null;
  uploadInputKey.value += 1;
}

function openFileDialog() {
  if (uploading.value || parsing.value) return;
  fileInputRef.value?.click();
}

function clearSelectedFile() {
  resetSelectedFile();
}

async function navigateToTab(tab: ResumeTab, resumeId: number | null = resume.value?.id ?? routeResumeId.value) {
  const query: Record<string, string> = { tab };
  if (resumeId) {
    query.resumeId = String(resumeId);
  }
  await router.push({ path: "/resumes", query });
}

async function ensureRouteState() {
  if (parseTab(route.query.tab)) {
    return true;
  }

  const query: Record<string, string> = { tab: defaultTab.value };
  if (routeResumeId.value) {
    query.resumeId = String(routeResumeId.value);
  }
  await router.replace({ path: "/resumes", query });
  return false;
}

async function syncSelectionFromRoute() {
  if (!routeResumeId.value) return;
  try {
    await resumeStore.selectResumeById(routeResumeId.value, {
      ensureParsed: activeTab.value === "analysis",
      fetchSummary: activeTab.value === "analysis",
    });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载简历失败");
  }
}

function onResumeChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
}

async function refreshLibrary() {
  try {
    await resumeStore.loadLibrary();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "刷新历史记录失败");
  }
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning("请先选择简历文件");
    return;
  }

  try {
    const result = await resumeStore.uploadAndParse(selectedFile.value);
    resetSelectedFile();
    ElMessage.success("简历已上传并完成分析");
    await navigateToTab("analysis", result.resume?.id ?? resume.value?.id ?? null);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "上传简历失败");
  }
}

async function openAnalysis(item: ResumeLibraryItem) {
  try {
    await resumeStore.selectResume(item, { ensureParsed: true, fetchSummary: true });
    await navigateToTab("analysis", item.id);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "打开分析失败");
  }
}

async function useForInterview(item: ResumeLibraryItem) {
  try {
    await resumeStore.selectResume(item, { fetchSummary: item.status === "parsed" || Boolean(item.summary) });
    await router.push({ path: "/interviews/new", query: { resumeId: String(item.id) } });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "选择简历失败");
  }
}

async function goToInterviewWithSelected() {
  const query = resume.value ? { resumeId: String(resume.value.id) } : undefined;
  await router.push({ path: "/interviews/new", query });
}

async function handleTabChange(name: string | number) {
  const tab = parseTab(name);
  if (!tab) return;
  await navigateToTab(tab);
}

async function goToUploadTab() {
  await navigateToTab("upload");
}

async function goToHistoryTab() {
  await navigateToTab("history");
}
</script>

<style scoped>
.resume-center-card {
  padding: 24px;
}

.header-row,
.header-actions,
.upload-actions,
.footer-row,
.history-head,
.match-head,
.summary-hero,
.hero-side {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.heading-copy {
  max-width: 760px;
}

.muted {
  margin: 0;
  color: var(--muted);
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
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(30, 60, 110, 0.08);
}

.summary-card.warm {
  background: linear-gradient(135deg, rgba(90, 169, 255, 0.10), rgba(255, 255, 255, 0.82));
}

.summary-card span {
  display: block;
  color: var(--muted);
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 24px;
  line-height: 1.4;
}

.resume-tabs {
  margin-top: 20px;
}

.tab-panel,
.analysis-stack {
  display: grid;
  gap: 16px;
}

.nested-card {
  padding: 20px;
  background: rgba(255, 255, 255, 0.56);
}

.upload-panel {
  gap: 18px;
}

.upload-copy h3,
.detail-card h3,
.match-card h4,
.history-card h3 {
  margin-bottom: 8px;
}

.hidden-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.upload-dropzone {
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 20px;
  border: 1px dashed rgba(90, 169, 255, 0.24);
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(90, 169, 255, 0.05), rgba(255, 255, 255, 0.76));
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.upload-dropzone:hover {
  transform: translateY(-1px);
  border-color: rgba(90, 169, 255, 0.34);
  box-shadow: var(--shadow-soft);
}

.upload-dropzone.filled {
  border-style: solid;
  background: linear-gradient(135deg, rgba(90, 169, 255, 0.10), rgba(255, 255, 255, 0.82));
}

.upload-dropzone.busy {
  opacity: 0.8;
}

.upload-icon {
  width: 56px;
  height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: var(--primary-soft);
  color: var(--primary);
}

.dropzone-copy strong {
  display: block;
  margin-bottom: 6px;
  font-size: 16px;
}

.dropzone-pill,
.summary-pill,
.match-score {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-weight: 700;
}

.dropzone-pill {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(30, 60, 110, 0.08);
  color: var(--primary);
  white-space: nowrap;
}

.format-row,
.token-list,
.record-actions,
.empty-actions,
.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.format-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(30, 60, 110, 0.08);
  color: var(--muted-strong);
  font-size: 12px;
  font-weight: 700;
}

.selected-file-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(30, 60, 110, 0.08);
}

.upload-actions {
  align-items: center;
}

.upload-note {
  flex: 1;
}

.hero-side {
  align-items: center;
}

.summary-pill {
  min-width: 102px;
  padding: 10px 16px;
  flex-direction: column;
  background: rgba(90, 169, 255, 0.10);
  color: var(--primary);
}

.score-grid,
.match-grid,
.analysis-columns,
.history-grid,
.history-stats {
  display: grid;
  gap: 16px;
}

.score-grid {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.match-grid,
.history-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.analysis-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.score-card,
.detail-card,
.history-card,
.match-card {
  border: 1px solid rgba(30, 60, 110, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.82);
}

.score-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-card span,
.history-stat span {
  color: var(--muted);
  font-size: 13px;
}

.score-card strong,
.history-stat strong,
.match-score {
  font-size: 22px;
  color: var(--primary);
}

.match-card.featured,
.history-card.selected {
  border-color: rgba(90, 169, 255, 0.30);
  box-shadow: 0 0 0 1px rgba(90, 169, 255, 0.14);
}

.match-summary,
.match-detail,
.detail-copy,
.history-summary {
  margin: 12px 0 0;
  line-height: 1.7;
}

.field-block {
  margin-top: 18px;
}

.token {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(240, 247, 255, 0.95);
  border: 1px solid rgba(30, 60, 110, 0.08);
  line-height: 1.5;
}

.success-token {
  background: rgba(90, 169, 255, 0.08);
  color: var(--primary);
}

.warning-token {
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.accent-token {
  background: rgba(90, 169, 255, 0.10);
  color: var(--primary);
}

.muted-token {
  color: var(--muted);
}

.history-stats {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 16px;
}

.history-stat {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(240, 247, 255, 0.88);
  border: 1px solid rgba(90, 169, 255, 0.08);
}

.resume-note {
  flex: 1;
}

.empty-card {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 980px) {
  .header-row,
  .header-actions,
  .summary-hero,
  .hero-side,
  .upload-actions,
  .footer-row,
  .history-head,
  .match-head,
  .selected-file-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-strip,
  .analysis-columns,
  .history-stats {
    grid-template-columns: 1fr;
  }

  .upload-dropzone {
    grid-template-columns: 1fr;
  }

  .dropzone-pill,
  .summary-pill {
    align-self: stretch;
  }
}
</style>
