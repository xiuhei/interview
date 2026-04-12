<script setup lang="ts">
/**
 * 面试房间页 — 语音面试核心页面
 *
 * 增强版：支持持续语音面试模式
 * - 候选人不需要手动点"结束回答"
 * - 系统自动检测回答结束
 * - 支持停顿思考、补充回答
 * - 可选"我说完了"快捷按钮
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElMessage, ElMessageBox } from 'element-plus'

import InterviewStatusPanel from '@/components/interview/InterviewStatusPanel.vue'
import SpeakingWave from '@/components/interview/SpeakingWave.vue'
import ListeningIndicator from '@/components/interview/ListeningIndicator.vue'

import { useWebSocketInterview } from '@/composables/useWebSocketInterview'
import { useMicrophone } from '@/composables/useMicrophone'
import { useTtsPlayer } from '@/composables/useTtsPlayer'

import type { InterviewRoomState } from '@/types/websocket'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.id as string
const jobName = (route.query.job as string) || '技术面试'
const style = (route.query.style as string) || 'medium'
const resumeSummary = (route.query.resume_summary as string) || null

// ---- Composables ----
const {
  connected,
  roomState,
  roundNo,
  error: wsError,
  continuousMode,
  connect: wsConnect,
  disconnect: wsDisconnect,
  sendAudioChunk,
  sendSpeakDone,
  sendEndInterview,
} = useWebSocketInterview()

const {
  isRecording,
  hasPermission,
  error: micError,
  start: startMic,
  stop: stopMic,
} = useMicrophone()

const {
  cancel: ttsCancel,
  playBase64: ttsPlayBase64,
  speakText: ttsSpeakText,
} = useTtsPlayer()

// ---- 状态计算 ----
const isInterviewerSpeaking = computed(() => roomState.value === 'interviewer_speaking')
const isListening = computed(() =>
  [
    'user_waiting',
    'user_speaking',
    'endpoint_detecting',
    'candidate_short_pause',
    'candidate_long_pause',
  ].includes(roomState.value)
)
const isCandidatePausing = computed(() =>
  ['candidate_short_pause', 'candidate_long_pause'].includes(roomState.value)
)
const isAnalyzing = computed(() =>
  [
    'answer_analyzing',
    'decision_making',
    'answer_finalizing',
    'followup_deciding',
  ].includes(roomState.value)
)
const isFinished = computed(() =>
  ['finished', 'interview_aborted'].includes(roomState.value)
)
const canEnd = computed(() =>
  !isFinished.value && roomState.value !== 'connecting' && roomState.value !== 'error'
)
const canForceEnd = computed(() => false)

const report = ref<Record<string, unknown> | null>(null)

// ---- 状态标签 ----
const listeningLabel = computed(() => {
  if (roomState.value === 'candidate_long_pause') return '正在思考中...'
  if (roomState.value === 'candidate_short_pause') return '正在思考中...'
  if (roomState.value === 'user_speaking') return '正在倾听...'
  return '请直接回答'
})

// ---- 初始化 ----
onMounted(async () => {
  wsConnect({
    sessionId,
    jobName,
    style,
    resumeSummary,
    onInterviewerSpeak: async (text, _isQuestion, audioBase64, mimeType) => {
      if (audioBase64) {
        await ttsPlayBase64(audioBase64, mimeType || 'audio/wav', {
          onEnd: () => {
            sendSpeakDone()
          },
          onError: () => {
            void ttsSpeakText(text, {
              onEnd: () => {
                sendSpeakDone()
              },
              onError: (message) => {
                ElMessage.error(message || '面试官语音播报失败')
              },
            })
          },
        })
        return
      }
      await ttsSpeakText(text, {
        onEnd: () => {
          sendSpeakDone()
        },
        onError: (message) => {
          ElMessage.error(message || '面试官语音播报失败')
        },
      })
    },
    onListening: async () => {
      // 开始监听 → 启动麦克风
      if (!isRecording.value) {
        await startMic({
          onAudioChunk: (b64) => {
            sendAudioChunk(b64)
          },
        })
      }
    },
    onReportReady: (r) => {
      report.value = r
      stopMic()
    },
    onError: (_code, msg) => {
      ElMessage.error(msg || '面试出现异常')
    },
    // 持续模式回调
    onSilenceNudge: (_text, _count) => {
      // 提醒已通过 onInterviewerSpeak 播放，此处可做额外 UI 展示
    },
    onContinuousMode: (enabled) => {
      if (enabled) {
        console.log('[面试] 持续语音对话模式已启用')
      }
    },
    onAnswerBoundary: (_roundNo, _confidence) => {
      // 系统已自动检测到回答结束
    },
  })
})

onUnmounted(() => {
  ttsCancel()
  stopMic()
  wsDisconnect()
})

function handleForceAnswerEnd() {}

// ---- 手动结束回答 ----
// ---- 结束面试 ----
async function handleEndInterview() {
  try {
    await ElMessageBox.confirm('确定要结束面试吗？', '提示', {
      confirmButtonText: '确定结束',
      cancelButtonText: '继续面试',
      type: 'warning',
    })
    ttsCancel()
    stopMic()
    sendEndInterview()
  } catch {
    // 用户取消
  }
}

function goToReport() {
  router.push(`/interviews/${sessionId}/report`)
}
</script>

<template>
  <div class="interview-room">
    <!-- 顶栏 -->
    <header class="room-header">
      <div class="header-left">
        <span class="room-title">语音面试</span>
        <span class="connection-dot" :class="{ online: connected }" />
        <span v-if="continuousMode" class="mode-badge">持续对话</span>
      </div>
      <ElButton
        v-if="canEnd"
        type="danger"
        plain
        size="small"
        @click="handleEndInterview"
      >
        结束面试
      </ElButton>
    </header>

    <!-- 主区域 -->
    <main class="room-body">
      <!-- 状态面板 -->
      <InterviewStatusPanel
        :state="roomState"
        :job-name="jobName"
        :round-no="roundNo"
      />

      <!-- 视觉反馈区 -->
      <div class="visual-area">
        <!-- 面试官说话波形 -->
        <div v-if="isInterviewerSpeaking" class="visual-block">
          <SpeakingWave :active="true" />
          <p class="visual-label">面试官正在发言</p>
        </div>

        <!-- 聆听指示器（含停顿思考状态） -->
        <div v-else-if="isListening" class="visual-block">
          <ListeningIndicator :active="true" />
          <p class="visual-label">{{ listeningLabel }}</p>
          <!-- 持续模式：可选"我说完了"按钮 -->
          <ElButton
            v-if="false"
            type="primary"
            plain
            size="small"
            class="done-btn"
            @click="handleForceAnswerEnd"
          >
            我说完了
          </ElButton>
        </div>

        <!-- 分析中 -->
        <div v-else-if="isAnalyzing" class="visual-block">
          <div class="analyzing-spinner" />
          <p class="visual-label">正在思考下一个问题</p>
        </div>

        <!-- 面试结束 -->
        <div v-else-if="isFinished" class="visual-block">
          <div class="finished-icon">&#10003;</div>
          <p class="visual-label">面试已结束</p>
          <ElButton type="primary" @click="goToReport" style="margin-top: 16px;">
            查看面试报告
          </ElButton>
        </div>

        <!-- 连接中/空闲 -->
        <div v-else class="visual-block">
          <div class="connecting-dots">
            <span /><span /><span />
          </div>
          <p class="visual-label">{{ roomState === 'connecting' ? '正在连接...' : '准备中' }}</p>
        </div>
      </div>

      <!-- 麦克风状态 -->
      <div class="mic-status" v-if="!isFinished">
        <span v-if="hasPermission && isRecording" class="mic-on">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/>
          </svg>
          麦克风已开启
        </span>
        <span v-else-if="micError" class="mic-error">{{ micError }}</span>
        <span v-else class="mic-off">麦克风待开启</span>
      </div>

      <!-- 错误提示 -->
      <div v-if="wsError" class="error-banner">
        {{ wsError }}
      </div>
    </main>
  </div>
</template>

<style scoped>
.interview-room {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg, #F5F9FF);
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--color-surface, rgba(245, 250, 255, 0.9));
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.room-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text, #1F2D3D);
}

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
  transition: background 0.3s;
}

.connection-dot.online {
  background: #22c55e;
}

.mode-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--color-primary, #5AA9FF);
  color: #fff;
  font-weight: 500;
}

.room-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  gap: 40px;
}

.visual-area {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
}

.visual-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.visual-label {
  font-size: 15px;
  color: var(--color-muted, #5B6B7B);
  margin: 0;
}

.done-btn {
  margin-top: 8px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.done-btn:hover {
  opacity: 1;
}

/* 分析中旋转动画 */
.analyzing-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(0, 0, 0, 0.08);
  border-top-color: var(--color-primary, #5AA9FF);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 完成图标 */
.finished-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-primary, #5AA9FF);
  color: #fff;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 连接中动画 */
.connecting-dots {
  display: flex;
  gap: 8px;
}

.connecting-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-muted, #5B6B7B);
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.connecting-dots span:nth-child(2) { animation-delay: 0.2s; }
.connecting-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 麦克风状态 */
.mic-status {
  font-size: 13px;
}

.mic-on {
  color: #22c55e;
  display: flex;
  align-items: center;
  gap: 4px;
}

.mic-off {
  color: var(--color-muted, #5B6B7B);
}

.mic-error {
  color: #dc2626;
}

.error-banner {
  background: #fef2f2;
  color: #dc2626;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
}
</style>
