/**
 * WebSocket 消息协议类型定义 — 与后端 schemas/websocket.py 对齐
 * 增强版：支持持续语音面试模式
 */

// ---- 前端 → 后端 ----

export type ClientMessageType =
  | 'session_start'
  | 'audio_chunk'
  | 'user_stop'
  | 'speak_done'
  | 'end_interview'
  | 'heartbeat'
  | 'force_answer_end'    // 持续模式：用户手动标记回答结束

export interface ClientMessage {
  type: ClientMessageType
  payload: Record<string, unknown>
}

// ---- 后端 → 前端 ----

export type ServerMessageType =
  | 'session_ready'
  | 'state_changed'
  | 'interviewer_speak'
  | 'listening'
  | 'report_ready'
  | 'error'
  | 'heartbeat_ack'
  | 'silence_nudge'       // 持续模式：沉默提醒
  | 'continuous_mode'      // 持续模式：通知前端模式状态
  | 'answer_boundary'      // 持续模式：检测到回答结束

export interface ServerMessage {
  type: ServerMessageType
  payload: Record<string, unknown>
}

// ---- 具体消息 payload 类型 ----

export interface SessionReadyPayload {
  session_id: string
}

export interface StateChangedPayload {
  state: string
  round_no: number
}

export interface InterviewerSpeakPayload {
  text: string
  is_question: boolean
  audio_base64?: string
  mime_type?: string
}

export interface ReportReadyPayload {
  report: Record<string, unknown>
}

export interface ErrorPayload {
  code: string
  message: string
}

// ---- 持续模式 payload ----

export interface SilenceNudgePayload {
  text: string
  reminder_count: number
}

export interface ContinuousModePayload {
  enabled: boolean
}

export interface AnswerBoundaryPayload {
  round_no: number
  confidence: number
}

// ---- 面试状态 ----

export type InterviewRoomState =
  | 'connecting'
  | 'idle'
  | 'preparing'
  | 'opening'
  | 'interviewer_speaking'
  | 'user_waiting'
  | 'user_speaking'
  | 'endpoint_detecting'
  | 'answer_analyzing'
  | 'decision_making'
  | 'closing'
  | 'finished'
  | 'error'
  // ---- 持续模式新增状态 ----
  | 'candidate_short_pause'
  | 'candidate_long_pause'
  | 'answer_finalizing'
  | 'followup_deciding'
  | 'asking_followup'
  | 'asking_next_question'
  | 'interview_ending'
  | 'interview_aborted'
