import { defineStore } from "pinia";

import type {
  AnswerEvaluation,
  InterviewDetail,
  InterviewNextStep,
  InterviewProgress,
  InterviewQuestion,
  InterviewReport,
  InterviewSession,
  QuestionPrefetch,
  ResumeSummary,
  SubmitAnswerResponse,
} from "@/types/models";

export const useInterviewStore = defineStore("interview", {
  state: () => ({
    session: null as InterviewSession | null,
    currentQuestion: null as InterviewQuestion | null,
    questionTrail: [] as InterviewQuestion[],
    evaluations: [] as AnswerEvaluation[],
    report: null as InterviewReport | null,
    resumeSummary: null as ResumeSummary | null,
    prefetch: null as QuestionPrefetch | null,
  }),
  actions: {
    startSession(session: InterviewSession, firstQuestion: InterviewQuestion, resumeSummary: ResumeSummary | null) {
      this.reset();
      this.session = session;
      this.resumeSummary = resumeSummary;
      this.upsertQuestion(firstQuestion);
      this.currentQuestion = firstQuestion;
    },
    hydrateFromDetail(detail: InterviewDetail) {
      this.reset();
      this.session = detail.session;
      this.resumeSummary = detail.resume_summary;
      this.questionTrail = [...detail.questions].sort((left, right) => left.turn_no - right.turn_no);
      this.currentQuestion = this.questionTrail.at(-1) || null;
    },
    setResumeSummary(summary: ResumeSummary | null) {
      this.resumeSummary = summary;
    },
    setReport(report: InterviewReport) {
      this.report = report;
    },
    setPrefetch(prefetch: QuestionPrefetch | null) {
      this.prefetch = prefetch;
    },
    clearPrefetch() {
      this.prefetch = null;
    },
    applySubmitResponse(payload: SubmitAnswerResponse) {
      this.applyProgress(payload.progress);
      if (payload.evaluation) {
        this.upsertEvaluation(payload.evaluation);
      }
    },
    applyNextStepResponse(payload: InterviewNextStep) {
      this.applyProgress(payload.progress);
      this.clearPrefetch();
      if (payload.next_question) {
        this.upsertQuestion(payload.next_question);
        this.currentQuestion = payload.next_question;
      } else {
        this.currentQuestion = null;
      }
    },
    applyProgress(progress: InterviewProgress) {
      if (!this.session) return;
      this.session.current_turn = progress.current_round;
      this.session.min_questions = progress.min_rounds;
      this.session.max_questions = progress.max_rounds;
    },
    upsertQuestion(question: InterviewQuestion) {
      const index = this.questionTrail.findIndex((item) => item.id === question.id);
      if (index >= 0) {
        this.questionTrail.splice(index, 1, question);
      } else {
        this.questionTrail.push(question);
        this.questionTrail.sort((left, right) => left.turn_no - right.turn_no);
      }
    },
    upsertEvaluation(evaluation: AnswerEvaluation) {
      const index = this.evaluations.findIndex((item) => item.answer_id === evaluation.answer_id);
      if (index >= 0) {
        this.evaluations.splice(index, 1, evaluation);
        return;
      }
      this.evaluations.push(evaluation);
    },
    reset() {
      this.session = null;
      this.currentQuestion = null;
      this.questionTrail = [];
      this.evaluations = [];
      this.report = null;
      this.resumeSummary = null;
      this.prefetch = null;
    },
  },
});
