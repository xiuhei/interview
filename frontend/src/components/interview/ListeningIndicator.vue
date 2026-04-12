<script setup lang="ts">
/**
 * 聆听指示器 — 正在聆听用户说话时的视觉反馈（呼吸圆环动画）
 */
defineProps<{
  active: boolean
}>()
</script>

<template>
  <div class="listening-indicator" :class="{ active }">
    <div class="ring ring-outer" />
    <div class="ring ring-inner" />
    <div class="mic-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z" fill="currentColor"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <line x1="8" y1="23" x2="16" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.listening-indicator {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring {
  position: absolute;
  border-radius: 50%;
  border: 2px solid var(--color-primary, #5AA9FF);
  opacity: 0.3;
}

.ring-outer {
  width: 80px;
  height: 80px;
}

.ring-inner {
  width: 60px;
  height: 60px;
}

.listening-indicator.active .ring-outer {
  animation: breathe 2s ease-in-out infinite;
}

.listening-indicator.active .ring-inner {
  animation: breathe 2s ease-in-out infinite 0.3s;
}

.mic-icon {
  color: var(--color-primary, #5AA9FF);
  z-index: 1;
}

.listening-indicator.active .mic-icon {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% {
    transform: scale(1);
    opacity: 0.3;
  }
  50% {
    transform: scale(1.15);
    opacity: 0.6;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
