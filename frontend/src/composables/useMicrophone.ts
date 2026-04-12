/**
 * 麦克风采集 composable
 * - 页面加载时申请麦克风权限
 * - 使用 AudioWorklet / ScriptProcessor 采集音频
 * - 按 chunk 间隔分块，转为 base64 通过回调发出
 * - 面试全程麦克风持续开启
 */

import { ref, onUnmounted } from 'vue'

const CHUNK_MS = 200
const SAMPLE_RATE = 16000

export interface MicrophoneOptions {
  onAudioChunk: (base64Data: string) => void
  chunkMs?: number
}

export function useMicrophone() {
  const isRecording = ref(false)
  const hasPermission = ref(false)
  const error = ref<string | null>(null)

  let stream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let processor: ScriptProcessorNode | null = null
  let source: MediaStreamAudioSourceNode | null = null
  let onChunkCallback: ((b64: string) => void) | null = null

  async function start(options: MicrophoneOptions): Promise<boolean> {
    onChunkCallback = options.onAudioChunk
    const chunkMs = options.chunkMs || CHUNK_MS

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: SAMPLE_RATE,
        },
      })
      hasPermission.value = true
    } catch (e) {
      error.value = '无法获取麦克风权限'
      hasPermission.value = false
      return false
    }

    try {
      audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
      source = audioContext.createMediaStreamSource(stream)

      // 计算 buffer 大小（近似 chunkMs）
      const bufferSize = Math.pow(2, Math.ceil(Math.log2(SAMPLE_RATE * chunkMs / 1000)))
      processor = audioContext.createScriptProcessor(
        Math.min(bufferSize, 16384), 1, 1
      )

      processor.onaudioprocess = (event) => {
        if (!isRecording.value) return
        const input = event.inputBuffer.getChannelData(0)
        // Float32 → Int16 PCM
        const pcm = float32ToInt16(input)
        // PCM → base64
        const b64 = arrayBufferToBase64(pcm.buffer)
        onChunkCallback?.(b64)
      }

      source.connect(processor)
      processor.connect(audioContext.destination)
      isRecording.value = true
      error.value = null
      return true
    } catch (e) {
      error.value = '音频初始化失败'
      return false
    }
  }

  function stop() {
    isRecording.value = false

    if (processor) {
      processor.disconnect()
      processor = null
    }
    if (source) {
      source.disconnect()
      source = null
    }
    if (audioContext) {
      audioContext.close()
      audioContext = null
    }
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      stream = null
    }
  }

  onUnmounted(() => {
    stop()
  })

  return {
    isRecording,
    hasPermission,
    error,
    start,
    stop,
  }
}

// ---- 工具函数 ----

function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return int16
}

function arrayBufferToBase64(buffer: ArrayBufferLike): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

