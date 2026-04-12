<template>
  <div class="panel-card recorder-panel">
    <div class="row">
      <strong>语音回答</strong>
      <el-tag :type="isRecording ? 'danger' : 'success'">{{ isRecording ? '录音中' : '待命' }}</el-tag>
    </div>
    <p class="tip">支持浏览器录音或直接上传音频文件，录音会提交到已接入的商用语音识别服务。</p>
    <div class="actions">
      <el-button v-if="!isRecording" @click="$emit('start')">开始录音</el-button>
      <el-button v-else type="danger" @click="$emit('stop')">停止录音</el-button>
      <input type="file" accept="audio/*" @change="handleFileChange" />
    </div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" show-icon :closable="false" />
  </div>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  (e: 'start'): void;
  (e: 'stop'): void;
  (e: 'file', file: File): void;
}>();

defineProps<{
  isRecording: boolean;
  errorMessage: string;
}>();

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) emit('file', file);
}
</script>

<style scoped>
.recorder-panel {
  padding: 18px;
}
.row,
.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
}
.tip {
  color: var(--muted);
  line-height: 1.6;
}
</style>
