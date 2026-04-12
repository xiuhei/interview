import { ref } from "vue";

import {
  createInterview,
  fetchAnswerEvaluation,
  fetchFirstQuestion,
  fetchInterviewReport,
  fetchNextQuestion,
  prefetchQuestion,
  submitAnswer,
  uploadAudio,
} from "@/api/interviews";
import { useInterviewStore } from "@/stores/interview";
import type { AnswerEvaluation, QuestionPrefetch, ResumeSummary } from "@/types/models";

const SCORE_POLL_INTERVAL_MS = 1500;
const SCORE_POLL_ATTEMPTS = 12;

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useInterviewFlow() {
  const loading = ref(false);
  const store = useInterviewStore();

  async function startInterview(payload: Record<string, unknown>, resumeSummary: ResumeSummary | null = null) {
    loading.value = true;
    try {
      const sessionResponse = await createInterview(payload);
      const questionResponse = await fetchFirstQuestion(sessionResponse.data.id);
      store.startSession(sessionResponse.data, questionResponse.data, resumeSummary);
      return sessionResponse.data;
    } finally {
      loading.value = false;
    }
  }

  async function submitTextAnswer(textAnswer: string) {
    if (!store.session || !store.currentQuestion) return null;
    const response = await submitAnswer(store.session.id, {
      question_id: store.currentQuestion.id,
      answer_mode: "text",
      text_answer: textAnswer,
    });
    store.applySubmitResponse(response.data);
    return response.data;
  }

  async function submitAudioAnswer(file: File) {
    if (!store.session || !store.currentQuestion) return null;
    const uploaded = await uploadAudio(file);
    const response = await submitAnswer(store.session.id, {
      question_id: store.currentQuestion.id,
      answer_mode: "audio",
      audio_file_id: uploaded.data.file_id,
    });
    store.applySubmitResponse(response.data);
    return response.data;
  }

  async function prefetchNextQuestion(questionId: number, partialAnswer: string, version?: number | null): Promise<QuestionPrefetch | null> {
    if (!store.session) return null;
    const response = await prefetchQuestion(store.session.id, questionId, {
      partial_answer: partialAnswer,
      partial_answer_version: version ?? null,
    });
    if (store.currentQuestion?.id === questionId) {
      store.setPrefetch(response.data);
      return response.data;
    }
    return null;
  }

  async function loadNextStep() {
    if (!store.session) return null;
    const response = await fetchNextQuestion(store.session.id);
    store.applyNextStepResponse(response.data);
    return response.data;
  }

  async function pollAnswerEvaluation(answerId: number): Promise<AnswerEvaluation | null> {
    if (!store.session) return null;
    for (let attempt = 0; attempt < SCORE_POLL_ATTEMPTS; attempt += 1) {
      const response = await fetchAnswerEvaluation(store.session.id, answerId);
      if (response.data.ready && response.data.evaluation) {
        store.upsertEvaluation(response.data.evaluation);
        return response.data.evaluation;
      }
      if (attempt < SCORE_POLL_ATTEMPTS - 1) {
        await delay(SCORE_POLL_INTERVAL_MS);
      }
    }
    return null;
  }

  async function refreshReport(sessionId: number) {
    const response = await fetchInterviewReport(sessionId);
    store.setReport(response.data);
    return response.data;
  }

  return {
    loading,
    startInterview,
    submitTextAnswer,
    submitAudioAnswer,
    prefetchNextQuestion,
    loadNextStep,
    pollAnswerEvaluation,
    refreshReport,
  };
}

