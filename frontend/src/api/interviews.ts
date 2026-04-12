import client from "./client";
import type {
  ActiveInterview,
  AnswerEvaluationStatus,
  ApiEnvelope,
  HistoryItem,
  HistoryInterviewDetail,
  InterviewDetail,
  InterviewNextStep,
  InterviewQuestion,
  InterviewReport,
  InterviewSession,
  QuestionPrefetch,
  QuestionPrefetchRequest,
  SubmitAnswerResponse,
} from "@/types/models";

export function createInterview(payload: Record<string, unknown>) {
  return client.post<never, ApiEnvelope<InterviewSession>>("/interviews", payload);
}

export function fetchActiveInterview() {
  return client.get<never, ApiEnvelope<ActiveInterview | null>>("/interviews/active");
}

export function discardInterview(sessionId: number) {
  return client.post<never, ApiEnvelope<{ session_id: number }>>(`/interviews/${sessionId}/discard`);
}

export function fetchFirstQuestion(sessionId: number) {
  return client.get<never, ApiEnvelope<InterviewQuestion>>(`/interviews/${sessionId}/first-question`);
}

export function uploadAudio(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return client.post<FormData, ApiEnvelope<{ file_id: string; url: string; stored_path: string }>>(
    "/interviews/audio/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
}

export function submitAnswer(sessionId: number, payload: Record<string, unknown>) {
  return client.post<never, ApiEnvelope<SubmitAnswerResponse>>(`/interviews/${sessionId}/answers`, payload);
}

export function prefetchQuestion(sessionId: number, questionId: number, payload: QuestionPrefetchRequest) {
  return client.post<never, ApiEnvelope<QuestionPrefetch>>(`/interviews/${sessionId}/questions/${questionId}/prefetch`, payload, {
    timeout: 12000,
  });
}

export function fetchAnswerEvaluation(sessionId: number, answerId: number) {
  return client.get<never, ApiEnvelope<AnswerEvaluationStatus>>(`/interviews/${sessionId}/answers/${answerId}/evaluation`);
}

export function fetchNextQuestion(sessionId: number) {
  return client.get<never, ApiEnvelope<InterviewNextStep>>(`/interviews/${sessionId}/next-question`, {
    timeout: 90000,
  });
}

export function fetchInterviewDetail(sessionId: number) {
  return client.get<never, ApiEnvelope<InterviewDetail>>(`/interviews/${sessionId}`);
}

export function completeInterview(sessionId: number) {
  return client.post<never, ApiEnvelope<InterviewReport>>(`/interviews/${sessionId}/complete`);
}

export function fetchInterviewReport(sessionId: number) {
  return client.get<never, ApiEnvelope<InterviewReport>>(`/interviews/${sessionId}/report`);
}

export function fetchHistory() {
  return client.get<never, ApiEnvelope<HistoryItem[]>>("/records/interviews");
}

export function fetchHistoryDetail(sessionId: number) {
  return client.get<never, ApiEnvelope<HistoryInterviewDetail>>(`/records/interviews/${sessionId}`);
}

export function deleteHistory(sessionId: number) {
  return client.delete<never, ApiEnvelope<{ session_id: number }>>(`/records/interviews/${sessionId}`);
}
