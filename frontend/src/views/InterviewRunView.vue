<template>
  <div class="run-layout" :class="{ 'single-column': isImmersiveMode }">
    <section class="panel-card main-panel">
      <!-- 顶栏 -->
      <div class="header-row">
        <div>
          <h2 class="session-title">{{ interviewStore.session?.title }}</h2>
        </div>
        <el-button
          type="danger"
          plain
          size="small"
          :disabled="finishing || submitting || waitingForBackend || !interviewStore.session"
          @click="handleFinish"
        >
          {{ finishing ? "处理中..." : "退出面试" }}
        </el-button>
      </div>

      <div v-if="!isImmersiveMode" class="chat-area" ref="chatAreaRef">
        <div class="chat-messages">
          <template v-for="(msg, idx) in chatMessages" :key="idx">
            <div v-if="msg.role === 'interviewer'" class="chat-bubble interviewer-bubble">
              <div class="bubble-avatar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.5"/>
                  <path d="M5 20c0-3.87 3.13-7 7-7s7 3.13 7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="bubble-content">
                <span class="bubble-tag" v-if="msg.competency">{{ msg.competency }}</span>
                <p>{{ msg.text }}</p>
              </div>
            </div>
            <div v-else class="chat-bubble user-bubble">
              <div class="bubble-content">
                <p>{{ msg.text }}</p>
                <span class="bubble-mode" v-if="msg.mode === 'audio'">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/>
                  </svg>
                  语音回答
                </span>
              </div>
            </div>
          </template>

          <div v-if="waitingForBackend" class="chat-bubble interviewer-bubble">
            <div class="bubble-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.5"/>
                <path d="M5 20c0-3.87 3.13-7 7-7s7 3.13 7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="bubble-content">
              <div class="typing-dots"><span /><span /><span /></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="immersive-stage">
        <div class="immersive-orb" :class="{ speaking: interviewerSpeaking, recording: isRecording, thinking: waitingForBackend }">
          <span class="orb-core"></span>
        </div>
        <p class="immersive-title">{{ immersiveStageLabel }}</p>
        <p class="immersive-copy">真实语音面试不显示题目文字、不展示过程记录，只保留当前语音交互状态。</p>
        <p v-if="errorMessage" class="immersive-warning">{{ errorMessage }}</p>
      </div>

      <!-- 输入区 -->
      <div class="chat-input-area">
        <!-- 语音录制模式 -->
        <div v-if="isImmersiveMode || inputMode === 'audio'" class="audio-input-bar">
          <button
            v-if="!isImmersiveMode"
            class="icon-btn mode-toggle"
            :disabled="answerInputLocked"
            @click="inputMode = 'text'"
            title="切换到文本"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M4 7h16M4 12h16M4 17h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <div class="audio-center" :class="{ recording: isRecording }">
            <button
              class="mic-main-btn"
              :class="{ recording: isRecording }"
              :disabled="interviewerSpeaking || waitingForBackend || submitting || finishing"
              @click="handleMicAction"
            >
              <svg v-if="!isRecording" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
              </svg>
              <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2"/>
              </svg>
            </button>
            <span class="audio-hint">{{ interviewerSpeaking ? '面试官播报中...' : isRecording ? '录制中，点击停止' : isImmersiveMode ? '请直接开始语音作答' : '点击开始录制' }}</span>
          </div>
          <div style="width: 36px" />
        </div>

        <!-- 文本输入模式 -->
        <div v-else class="text-input-bar">
          <button class="icon-btn mode-toggle" :disabled="answerInputLocked" @click="inputMode = 'audio'" title="切换到语音">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z" stroke="currentColor" stroke-width="1.5"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <textarea
            ref="textareaRef"
            v-model="textAnswer"
            class="chat-textarea"
            :disabled="answerInputLocked"
            :placeholder="textInputPlaceholder"
            rows="1"
            @keydown.enter.exact.prevent="handleTextSubmit"
            @input="autoResizeTextarea"
          />
          <button
            class="icon-btn send-btn"
            :disabled="!textAnswer.trim() || answerInputLocked"
            @click="handleTextSubmit"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
        <p v-if="textInputStatus" class="input-status">{{ textInputStatus }}</p>
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { discardInterview, fetchInterviewDetail } from "@/api/interviews";
import { useInterviewFlow } from "@/composables/useInterviewFlow";
import { useRecorder } from "@/composables/useRecorder";
import { useTtsPlayer } from "@/composables/useTtsPlayer";
import { useInterviewStore } from "@/stores/interview";
import type { InterviewQuestion, SubmitAnswerResponse } from "@/types/models";

const PREFETCH_DEBOUNCE_MS = 900;
const PREFETCH_MIN_ANSWER_CHARS = 24;

const route = useRoute();
const router = useRouter();
const interviewStore = useInterviewStore();
const { submitTextAnswer, submitAudioAnswer, prefetchNextQuestion, loadNextStep, pollAnswerEvaluation } = useInterviewFlow();
const { isRecording, errorMessage, start, stop, reset, cleanup } = useRecorder();
const { cancel: cancelTts, speakText } = useTtsPlayer();

const textAnswer = ref("");
const submitting = ref(false);
const finishing = ref(false);
const interviewerSpeaking = ref(false);
const waitingForBackend = ref(false);
const evaluationPending = ref(false);
const prefetching = ref(false);
const prefetchVersion = ref(0);
const inputMode = ref<"text" | "audio">("text");
const chatAreaRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const draftQuestionId = ref<number | null>(null);
let prefetchTimer: number | null = null;
let speechErrorNotified = false;

interface ChatMessage {
  role: "interviewer" | "user";
  text: string;
  competency?: string;
  mode?: "text" | "audio";
}

interface PendingAnswerMessage {
  text: string;
  mode: "text" | "audio";
}

const pendingAnswers = ref<Record<number, PendingAnswerMessage>>({});

const isImmersiveMode = computed(() => interviewStore.session?.answer_mode === "audio");
const currentRound = computed(
  () => interviewStore.currentQuestion?.round_no ?? interviewStore.session?.current_turn ?? 0,
);
const answerInputLocked = computed(
  () => submitting.value || waitingForBackend.value || finishing.value || !interviewStore.currentQuestion,
);
const textInputPlaceholder = computed(() => {
  if (submitting.value) return "正在提交当前回答...";
  if (waitingForBackend.value) return "正在生成下一题，请等题目出现后再回答";
  if (!interviewStore.currentQuestion) return "正在加载题目...";
  if (finishing.value) return "正在结束面试...";
  return "输入你的回答...";
});
const textInputStatus = computed(() => {
  if (submitting.value) return "当前回答正在提交，暂时不能继续输入。";
  if (waitingForBackend.value) return "下一题生成中，请等题目展示后再作答。";
  if (!interviewStore.currentQuestion) return "正在加载题目，请稍候。";
  return "";
});
const immersiveStageLabel = computed(() => {
  if (interviewerSpeaking.value) return "面试官正在语音播报";
  if (waitingForBackend.value) return "系统正在分析你的回答";
  if (isRecording.value) return "正在采集你的语音回答";
  if (submitting.value) return "正在提交语音回答";
  return "准备进入下一轮语音提问";
});

const chatMessages = computed<ChatMessage[]>(() => {
  const messages: ChatMessage[] = [];
  const trail = interviewStore.questionTrail;

  for (const q of trail) {
    messages.push({
      role: "interviewer",
      text: q.question_text,
      competency: q.competency_code || undefined,
    });
    const ev = interviewStore.evaluations.find((e) => e.question_id === q.id);
    if (ev?.answer_text) {
      messages.push({ role: "user", text: ev.answer_text, mode: "text" });
    } else if (ev?.asr_text) {
      messages.push({ role: "user", text: ev.asr_text, mode: "audio" });
    } else if (pendingAnswers.value[q.id]) {
      messages.push({ role: "user", text: pendingAnswers.value[q.id].text, mode: pendingAnswers.value[q.id].mode });
    }
  }

  return messages;
});

watch(chatMessages, () => {
  nextTick(() => scrollToBottom());
});

watch(
  isImmersiveMode,
  (value) => {
    if (value) {
      inputMode.value = "audio";
    }
  },
  { immediate: true },
);

watch(
  () => interviewStore.currentQuestion?.id,
  (questionId) => {
    clearPrefetchTimer();
    prefetchVersion.value = 0;
    interviewStore.clearPrefetch();
    if (draftQuestionId.value !== null && draftQuestionId.value !== questionId && textAnswer.value.trim()) {
      textAnswer.value = "";
      nextTick(() => autoResizeTextarea());
    }
    draftQuestionId.value = questionId ?? null;
    if (!questionId) {
      prefetching.value = false;
      return;
    }
    void warmupPrefetch(questionId);
    if (interviewStore.currentQuestion) {
      void speakQuestion(interviewStore.currentQuestion);
    }
  },
  { immediate: true },
);

watch(textAnswer, (value) => {
  if (value.trim() && interviewStore.currentQuestion?.id) {
    draftQuestionId.value = interviewStore.currentQuestion.id;
  }
  schedulePrefetch(value);
});

onMounted(async () => {
  if (!interviewStore.session || interviewStore.session.id !== Number(route.params.id) || !interviewStore.questionTrail.length) {
    const detail = (await fetchInterviewDetail(Number(route.params.id))).data;
    interviewStore.hydrateFromDetail(detail);
  }
  if (isImmersiveMode.value) {
    inputMode.value = "audio";
  }
  await reconcileNextStep(false);
});

onBeforeUnmount(() => {
  clearPrefetchTimer();
  cancelSpeech();
  cleanup();
});

function scrollToBottom() {
  if (chatAreaRef.value) {
    chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight;
  }
}

function autoResizeTextarea() {
  if (textareaRef.value) {
    textareaRef.value.style.height = "auto";
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + "px";
  }
}

function clearPrefetchTimer() {
  if (prefetchTimer !== null) {
    window.clearTimeout(prefetchTimer);
    prefetchTimer = null;
  }
}

function cancelSpeech() {
  interviewerSpeaking.value = false;
  cancelTts();
}

async function speakQuestion(question: InterviewQuestion | null) {
  if (!question) return;
  cancelSpeech();
  await speakText(question.question_text, {
    onStart: () => {
      interviewerSpeaking.value = true;
    },
    onEnd: async () => {
      interviewerSpeaking.value = false;
      if (isImmersiveMode.value && !isRecording.value && !waitingForBackend.value && !submitting.value && !finishing.value) {
        await start();
        if (errorMessage.value) {
          ElMessage.warning(errorMessage.value);
        }
      }
    },
    onError: (message) => {
      interviewerSpeaking.value = false;
      if (!speechErrorNotified) {
        speechErrorNotified = true;
        ElMessage.warning(message || "语音播报失败，请稍后重试");
      }
    },
  });
}

async function requestPrefetch(questionId: number, partialAnswer: string, version: number) {
  if (!interviewStore.currentQuestion || interviewStore.currentQuestion.id !== questionId) return;
  prefetching.value = true;
  try {
    await prefetchNextQuestion(questionId, partialAnswer, version);
  } catch {
    // prefetch failure is non-blocking
  } finally {
    if (!partialAnswer || version >= prefetchVersion.value) {
      prefetching.value = false;
    }
  }
}

async function warmupPrefetch(questionId: number) {
  await requestPrefetch(questionId, "", 0);
}

function schedulePrefetch(value: string) {
  if (isImmersiveMode.value || submitting.value || waitingForBackend.value || !interviewStore.currentQuestion) return;
  clearPrefetchTimer();
  const trimmed = value.trim();
  if (!trimmed || trimmed.length < PREFETCH_MIN_ANSWER_CHARS) return;
  const currentQuestionId = interviewStore.currentQuestion.id;
  const version = prefetchVersion.value + 1;
  prefetchVersion.value = version;
  prefetchTimer = window.setTimeout(() => {
    if (interviewStore.currentQuestion?.id !== currentQuestionId) return;
    void requestPrefetch(currentQuestionId, trimmed, version);
  }, PREFETCH_DEBOUNCE_MS);
}

async function reconcileNextStep(showSuccessMessage: boolean, answerId?: number) {
  if (!interviewStore.session) return null;
  waitingForBackend.value = true;
  try {
    const response = await loadNextStep();
    if (response?.next_action === "completed" && interviewStore.session?.id) {
      router.push(`/interviews/${interviewStore.session.id}/report`);
      return response;
    }
    if (showSuccessMessage) {
      ElMessage.success("已收到下一道题");
    }
    if (answerId) {
      void syncAnswerEvaluation(answerId);
    }
    return response;
  } catch (error) {
    if (showSuccessMessage) {
      ElMessage.error("答案已保存，但获取下一题失败，请稍后重试");
    } else if (error instanceof Error) {
      ElMessage.error(error.message);
    }
    return null;
  } finally {
    waitingForBackend.value = false;
  }
}

async function syncAnswerEvaluation(answerId: number) {
  evaluationPending.value = true;
  try {
    const evaluation = await pollAnswerEvaluation(answerId);
    if (!evaluation) {
      ElMessage.info("当前题评分仍在后台整理，稍后会自动更新");
    }
  } catch {
    ElMessage.info("当前题评分仍在后台整理，稍后会自动更新");
  } finally {
    evaluationPending.value = false;
  }
}

async function handleSavedAnswer(response: SubmitAnswerResponse | null) {
  if (!response) return;
  await reconcileNextStep(true, response.answer_id);
}

async function handleTextSubmit() {
  if (isImmersiveMode.value) {
    ElMessage.warning("真实语音面试仅支持语音作答");
    return;
  }
  if (answerInputLocked.value) {
    if (waitingForBackend.value || submitting.value) {
      ElMessage.info("下一题生成中，请等题目出现后再作答");
    }
    return;
  }
  const submittedText = textAnswer.value.trim();
  const submittedQuestionId = interviewStore.currentQuestion?.id;
  if (!submittedText || !submittedQuestionId) return;
  cancelSpeech();
  clearPrefetchTimer();
  submitting.value = true;
  let response: SubmitAnswerResponse | null = null;
  try {
    response = await submitTextAnswer(submittedText);
    pendingAnswers.value = {
      ...pendingAnswers.value,
      [submittedQuestionId]: {
        text: submittedText,
        mode: "text",
      },
    };
    textAnswer.value = "";
    if (textareaRef.value) {
      textareaRef.value.style.height = "auto";
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交失败");
  } finally {
    submitting.value = false;
  }
  await handleSavedAnswer(response);
}

async function handleMicAction() {
  if (waitingForBackend.value || submitting.value || finishing.value) return;
  if (interviewerSpeaking.value) return;
  cancelSpeech();
  if (isRecording.value) {
    const blob = await stop();
    await submitRecordedAudio(blob);
    return;
  }
  await start();
  if (errorMessage.value) {
    ElMessage.warning(errorMessage.value);
  }
}

async function submitRecordedAudio(blob: Blob | null) {
  if (!blob) return;
  clearPrefetchTimer();
  submitting.value = true;
  let response: SubmitAnswerResponse | null = null;
  try {
    const file = new File([blob], `recording-${Date.now()}.webm`, { type: blob.type || "audio/webm" });
    response = await submitAudioAnswer(file);
    reset();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "语音提交失败");
  } finally {
    submitting.value = false;
  }
  await handleSavedAnswer(response);
}

async function prepareFinish() {
  clearPrefetchTimer();
  cancelSpeech();
  if (isRecording.value) {
    await stop();
  }
  cleanup();
  reset();
}

async function handleFinish() {
  if (!interviewStore.session || finishing.value) return;
  if (submitting.value || waitingForBackend.value) {
    ElMessage.warning("当前答案仍在处理中，请稍候再结束面试");
    return;
  }
  finishing.value = true;
  try {
    await ElMessageBox.confirm(
      "题目没有全部回答完的面试会视为待完成。你可以保留 48 小时后继续作答，或直接删除这场未完成面试。",
      "退出待完成面试",
      {
        type: "warning",
        confirmButtonText: "保留 48 小时",
        cancelButtonText: "结束并删除",
        distinguishCancelAndClose: true,
        closeOnClickModal: false,
        closeOnPressEscape: false,
      },
    );
    await prepareFinish();
    ElMessage.success("这场面试已保留为待完成状态，48 小时内可以继续作答");
    router.push("/interviews/new");
  } catch (error) {
    if (error === "cancel") {
      try {
        const sessionId = Number(route.params.id);
        await discardInterview(sessionId);
        await prepareFinish();
        ElMessage.success("未完成面试已删除");
        router.push("/interviews/new");
      } catch (discardError) {
        ElMessage.error(discardError instanceof Error ? discardError.message : "删除未完成面试失败");
      }
    } else if (error !== "close") {
      ElMessage.error(error instanceof Error ? error.message : "退出面试失败");
    }
  } finally {
    finishing.value = false;
  }
}
</script>

<style scoped>
.run-layout {
  display: grid;
  grid-template-columns: 1.35fr 0.65fr;
  gap: 16px;
}
.run-layout.single-column {
  grid-template-columns: minmax(0, 1fr);
}

.immersive-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 32px 24px;
  text-align: center;
}

.immersive-orb {
  position: relative;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 30% 30%, rgba(15, 118, 110, 0.2), rgba(201, 111, 61, 0.1));
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
}

.orb-core {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0f766e, #c96f3d);
}

.immersive-orb.speaking {
  animation: orb-pulse 1.2s ease-in-out infinite;
}

.immersive-orb.recording {
  animation: orb-breathe 1.4s ease-in-out infinite;
}

.immersive-orb.thinking {
  animation: orb-rotate 2.6s linear infinite;
}

.immersive-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.immersive-copy,
.immersive-warning {
  max-width: 520px;
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.immersive-warning {
  color: var(--accent);
}

@keyframes orb-pulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.12); }
  50% { transform: scale(1.05); box-shadow: 0 0 0 18px rgba(15, 118, 110, 0.04); }
}

@keyframes orb-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

@keyframes orb-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.main-panel {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);
  overflow: hidden;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.session-title {
  margin: 0;
  font-size: 16px;
}

.muted {
  color: var(--muted);
  margin: 4px 0 0;
  font-size: 13px;
}

/* ---- 聊天区域 ---- */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---- 聊天气泡 ---- */
.chat-bubble {
  display: flex;
  gap: 10px;
  max-width: 80%;
}

.interviewer-bubble {
  align-self: flex-start;
}

.user-bubble {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.bubble-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-content {
  padding: 12px 16px;
  border-radius: 18px;
  line-height: 1.6;
}

.interviewer-bubble .bubble-content {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}

.user-bubble .bubble-content {
  background: var(--primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.bubble-content p {
  margin: 0;
  font-size: 14px;
}

.bubble-tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--primary-soft);
  color: var(--primary);
  margin-bottom: 6px;
}

.bubble-mode {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  opacity: 0.75;
  margin-top: 4px;
}

/* ---- 打字指示器 ---- */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
  animation: typing 1.2s ease-in-out infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

/* ---- 输入区域 ---- */
.chat-input-area {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  background: var(--surface-strong, #fff9f2);
}

.text-input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.chat-textarea {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  background: #fff;
  font-family: inherit;
  max-height: 120px;
  transition: border-color 0.2s;
}

.chat-textarea:focus {
  border-color: var(--primary);
}

.chat-textarea:disabled {
  background: rgba(255, 255, 255, 0.68);
  color: var(--muted);
  cursor: not-allowed;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.icon-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--ink);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.send-btn {
  background: var(--primary);
  color: #fff;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ---- 语音输入 ---- */
.audio-input-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
}

.audio-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.audio-center.recording {
  animation: pulse-bg 1.5s ease-in-out infinite;
}

.mic-main-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 16px rgba(15, 118, 110, 0.25);
}

.mic-main-btn.recording {
  background: #dc2626;
  box-shadow: 0 4px 16px rgba(220, 38, 38, 0.3);
}

.mic-main-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.mic-main-btn:disabled {
  opacity: 0.4;
  cursor: default;
  transform: none;
}

.audio-hint {
  font-size: 12px;
  color: var(--muted);
}

.input-status {
  margin: 8px 4px 0;
  font-size: 12px;
  color: var(--muted);
}

@keyframes pulse-bg {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

@media (max-width: 980px) {
  .run-layout {
    grid-template-columns: 1fr;
  }

  .main-panel {
    height: calc(100vh - 80px);
  }
}
</style>






