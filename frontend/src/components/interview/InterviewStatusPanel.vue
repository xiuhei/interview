<script setup lang="ts">
/**
 * 面试状态面板 — 显示当前状态文字、岗位、轮次
 */
import type { InterviewRoomState } from '@/types/websocket'

const props = defineProps<{
  state: InterviewRoomState
  jobName: string
  roundNo: number
}>()

const stateLabels: Record<string, string> = {
  connecting: '正在连接...',
  idle: '准备中',
  preparing: '正在准备面试...',
  opening: '面试即将开始...',
  interviewer_speaking: '面试官正在发言',
  user_waiting: '正在聆听你的回答',
  user_speaking: '正在聆听中...',
  endpoint_detecting: '正在聆听中...',
  answer_analyzing: '正在思考...',
  decision_making: '正在思考...',
  closing: '面试即将结束',
  finished: '面试已结束',
  error: '出现异常',
}
</script>

<template>
  <div class="status-panel">
    <div class="status-meta">
      <span class="job-tag">{{ jobName }}</span>
      <span class="round-tag" v-if="roundNo > 0">
        第 {{ roundNo }} 轮
      </span>
    </div>
    <div class="status-text" :class="state">
      {{ stateLabels[state] || state }}
    </div>
  </div>
</template>

<style scoped>
.status-panel {
  text-align: center;
}

.status-meta {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
}

.job-tag,
.round-tag {
  font-size: 13px;
  color: var(--color-muted, #6a5d52);
  background: rgba(0, 0, 0, 0.04);
  padding: 4px 12px;
  border-radius: 12px;
}

.status-text {
  font-size: 18px;
  font-weight: 500;
  color: var(--color-text, #1f1a17);
  transition: color 0.3s;
}

.status-text.interviewer_speaking {
  color: var(--color-primary, #0f766e);
}

.status-text.user_waiting,
.status-text.user_speaking {
  color: var(--color-accent, #c96f3d);
}

.status-text.answer_analyzing,
.status-text.decision_making {
  color: var(--color-muted, #6a5d52);
}

.status-text.finished {
  color: var(--color-primary, #0f766e);
}

.status-text.error {
  color: #dc2626;
}
</style>
