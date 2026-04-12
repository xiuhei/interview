<script setup lang="ts">
/**
 * 语音波形动画组件 — 面试官正在说话时的视觉反馈
 */
defineProps<{
  active: boolean
  color?: string
}>()
</script>

<template>
  <div class="speaking-wave" :class="{ active }">
    <span v-for="i in 5" :key="i" class="bar" :style="{ animationDelay: `${i * 0.1}s` }" />
  </div>
</template>

<style scoped>
.speaking-wave {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 40px;
}

.bar {
  width: 4px;
  height: 8px;
  border-radius: 2px;
  background: var(--color-primary, #0f766e);
  transition: height 0.2s ease;
}

.speaking-wave.active .bar {
  animation: wave 0.8s ease-in-out infinite alternate;
}

.speaking-wave.active .bar:nth-child(1) { animation-delay: 0s; }
.speaking-wave.active .bar:nth-child(2) { animation-delay: 0.1s; }
.speaking-wave.active .bar:nth-child(3) { animation-delay: 0.2s; }
.speaking-wave.active .bar:nth-child(4) { animation-delay: 0.3s; }
.speaking-wave.active .bar:nth-child(5) { animation-delay: 0.4s; }

@keyframes wave {
  0% { height: 8px; }
  100% { height: 32px; }
}
</style>
