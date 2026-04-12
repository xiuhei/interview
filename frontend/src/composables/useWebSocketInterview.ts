/**
 * WebSocket 面试通信 composable
 * - 建立/管理 WebSocket 连接
 * - 统一消息分发（按 type 路由）
 * - 发送音频块、心跳
 * - 断线自动重连
 * - 支持持续语音面试模式
 */

import { ref, onUnmounted } from 'vue'
import type {
  ClientMessage,
  ServerMessage,
  InterviewRoomState,
  InterviewerSpeakPayload,
  StateChangedPayload,
  ReportReadyPayload,
  ErrorPayload,
  SilenceNudgePayload,
  ContinuousModePayload,
  AnswerBoundaryPayload,
} from '@/types/websocket'

const HEARTBEAT_INTERVAL = 15_000  // 15s
const RECONNECT_DELAY = 3_000      // 3s
const MAX_RECONNECT = 5

export interface WebSocketInterviewOptions {
  sessionId: string
  jobName: string
  style?: string
  resumeSummary?: string | null
  competencies?: string[]
  onStateChanged?: (state: string, roundNo: number) => void
  onInterviewerSpeak?: (text: string, isQuestion: boolean, audioBase64?: string, mimeType?: string) => void
  onListening?: () => void
  onReportReady?: (report: Record<string, unknown>) => void
  onError?: (code: string, message: string) => void
  // 持续模式回调
  onSilenceNudge?: (text: string, reminderCount: number) => void
  onContinuousMode?: (enabled: boolean) => void
  onAnswerBoundary?: (roundNo: number, confidence: number) => void
}

export function useWebSocketInterview() {
  const connected = ref(false)
  const roomState = ref<InterviewRoomState>('connecting')
  const roundNo = ref(0)
  const error = ref<string | null>(null)
  const continuousMode = ref(false)

  let ws: WebSocket | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectCount = 0
  let options: WebSocketInterviewOptions | null = null
  let intentionalClose = false

  function connect(opts: WebSocketInterviewOptions) {
    options = opts
    intentionalClose = false
    _createConnection()
  }

  function _createConnection() {
    if (!options) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/interview/${options.sessionId}`

    roomState.value = 'connecting'
    error.value = null

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      reconnectCount = 0
      _startHeartbeat()

      // 发送 session_start
      _send({
        type: 'session_start',
        payload: {
          session_id: options!.sessionId,
          job_name: options!.jobName,
          style: options!.style || 'medium',
          resume_summary: options!.resumeSummary || null,
          competencies: options!.competencies || [],
        },
      })
    }

    ws.onmessage = (event) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data)
        _dispatch(msg)
      } catch {
        console.warn('[WS] 消息解析失败', event.data)
      }
    }

    ws.onclose = () => {
      connected.value = false
      _stopHeartbeat()
      if (!intentionalClose && reconnectCount < MAX_RECONNECT) {
        reconnectCount++
        console.log(`[WS] 断线重连 ${reconnectCount}/${MAX_RECONNECT}`)
        setTimeout(() => _createConnection(), RECONNECT_DELAY)
      }
    }

    ws.onerror = (e) => {
      console.error('[WS] 错误', e)
      error.value = '连接异常'
    }
  }

  function _dispatch(msg: ServerMessage) {
    switch (msg.type) {
      case 'session_ready':
        roomState.value = 'idle'
        break

      case 'state_changed': {
        const p = msg.payload as unknown as StateChangedPayload
        roomState.value = p.state as InterviewRoomState
        roundNo.value = p.round_no
        options?.onStateChanged?.(p.state, p.round_no)
        break
      }

      case 'interviewer_speak': {
        const p = msg.payload as unknown as InterviewerSpeakPayload
        roomState.value = 'interviewer_speaking'
        options?.onInterviewerSpeak?.(p.text, p.is_question, p.audio_base64, p.mime_type)
        break
      }

      case 'listening':
        roomState.value = 'user_waiting'
        options?.onListening?.()
        break

      case 'report_ready': {
        const p = msg.payload as unknown as ReportReadyPayload
        roomState.value = 'finished'
        options?.onReportReady?.(p.report)
        break
      }

      case 'error': {
        const p = msg.payload as unknown as ErrorPayload
        error.value = p.message
        options?.onError?.(p.code, p.message)
        break
      }

      case 'heartbeat_ack':
        break

      // ---- 持续模式新消息 ----

      case 'silence_nudge': {
        const p = msg.payload as unknown as SilenceNudgePayload
        options?.onSilenceNudge?.(p.text, p.reminder_count)
        // 沉默提醒也通过 interviewer_speak 播放
        break
      }

      case 'continuous_mode': {
        const p = msg.payload as unknown as ContinuousModePayload
        continuousMode.value = p.enabled
        options?.onContinuousMode?.(p.enabled)
        break
      }

      case 'answer_boundary': {
        const p = msg.payload as unknown as AnswerBoundaryPayload
        options?.onAnswerBoundary?.(p.round_no, p.confidence)
        break
      }

      default:
        console.warn('[WS] 未知消息类型', msg.type)
    }
  }

  function sendAudioChunk(base64Data: string) {
    _send({ type: 'audio_chunk', payload: { data: base64Data } })
  }

  function sendSpeakDone() {
    _send({ type: 'speak_done', payload: {} })
  }

  function sendEndInterview() {
    _send({ type: 'end_interview', payload: {} })
  }

  function sendForceAnswerEnd() {
    _send({ type: 'force_answer_end', payload: {} })
  }

  function disconnect() {
    intentionalClose = true
    _stopHeartbeat()
    ws?.close()
    ws = null
    connected.value = false
  }

  function _send(msg: ClientMessage) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
    }
  }

  function _startHeartbeat() {
    _stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      _send({ type: 'heartbeat', payload: {} })
    }, HEARTBEAT_INTERVAL)
  }

  function _stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    roomState,
    roundNo,
    error,
    continuousMode,
    connect,
    disconnect,
    sendAudioChunk,
    sendSpeakDone,
    sendEndInterview,
    sendForceAnswerEnd,
  }
}
