/**
 * 浏览器 TTS 播报 composable
 * - 使用 Web Speech API (SpeechSynthesisUtterance)
 * - 维护播放队列（避免多句话重叠）
 * - 播放完毕后回调通知（触发 speak_done）
 */

import { ref } from 'vue'

export interface SpeechSynthesisOptions {
  lang?: string
  rate?: number
  pitch?: number
  volume?: number
  onStart?: () => void
  onEnd?: () => void
  onError?: (error: string) => void
}

export function useSpeechSynthesis() {
  const isSpeaking = ref(false)
  const queue = ref<string[]>([])

  let currentOptions: SpeechSynthesisOptions = {}
  let isProcessing = false

  function configure(options: SpeechSynthesisOptions) {
    currentOptions = { ...options }
  }

  function speak(text: string) {
    queue.value.push(text)
    if (!isProcessing) {
      _processQueue()
    }
  }

  function cancel() {
    window.speechSynthesis.cancel()
    queue.value = []
    isSpeaking.value = false
    isProcessing = false
  }

  async function _processQueue() {
    if (isProcessing || queue.value.length === 0) return
    isProcessing = true

    while (queue.value.length > 0) {
      const text = queue.value.shift()!
      await _speakOne(text)
    }

    isProcessing = false
    // 所有播报完毕
    currentOptions.onEnd?.()
  }

  function _speakOne(text: string): Promise<void> {
    return new Promise((resolve) => {
      const synth = window.speechSynthesis

      // 某些浏览器需要先 cancel 才能播放新的
      if (synth.speaking) {
        synth.cancel()
      }

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = currentOptions.lang || 'zh-CN'
      utterance.rate = currentOptions.rate || 1.0
      utterance.pitch = currentOptions.pitch || 1.0
      utterance.volume = currentOptions.volume || 1.0

      // 尝试选择中文语音
      const voices = synth.getVoices()
      const zhVoice = voices.find(
        (v) => v.lang.startsWith('zh') && v.localService
      ) || voices.find((v) => v.lang.startsWith('zh'))
      if (zhVoice) {
        utterance.voice = zhVoice
      }

      utterance.onstart = () => {
        isSpeaking.value = true
        currentOptions.onStart?.()
      }

      utterance.onend = () => {
        isSpeaking.value = false
        resolve()
      }

      utterance.onerror = (event) => {
        isSpeaking.value = false
        currentOptions.onError?.(event.error)
        resolve()
      }

      synth.speak(utterance)
    })
  }

  return {
    isSpeaking,
    queue,
    configure,
    speak,
    cancel,
  }
}
