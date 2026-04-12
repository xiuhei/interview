export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  request_id: string;
}

export interface UserProfile {
  id: number;
  email: string;
  username: string;
  full_name: string;
  role: "user" | "admin";
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface CompetencyDimension {
  id: number;
  code: string;
  name: string;
  description: string;
  weight: number;
  is_required: boolean;
}

export interface JobPosition {
  id: number;
  code: string;
  name: string;
  description: string;
  weight_config: Record<string, number>;
  question_count_default: number;
}

export interface PositionDetail extends JobPosition {
  competencies: CompetencyDimension[];
}

export interface ResumeRead {
  id: number;
  filename: string;
  stored_path: string;
  mime_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeScoreBreakdown {
  clarity: number;
  project_depth: number;
  impact: number;
  role_relevance: number;
  credibility: number;
}

export interface ResumeJobMatch {
  position_code: string;
  position_name: string;
  score: number;
  level: string;
  matched_skills: string[];
  missing_skills: string[];
  matched_projects: string[];
  interview_focuses: string[];
  summary: string;
}

export interface ResumeSummary {
  candidate_name?: string | null;
  background: string;
  project_experiences: string[];
  tech_stack: string[];
  highlights: string[];
  risk_points: string[];
  years_of_experience?: number | null;
  overall_score: number;
  score_breakdown: ResumeScoreBreakdown;
  job_matches: ResumeJobMatch[];
  best_job_match?: ResumeJobMatch | null;
  resume_suggestions: string[];
  interview_focuses: string[];
}

export interface ResumeLibraryItem extends ResumeRead {
  summary?: ResumeSummary | null;
}

export interface InterviewCapabilities {
  llm_ready: boolean;
  embedding_ready: boolean;
  speech_ready: boolean;
  tts_ready: boolean;
  immersive_voice_interview_ready: boolean;
  llm_provider: string;
  embedding_provider: string;
  tts_provider: string;
  tts_model: string;
  tts_voice: string;
}

export interface InterviewSession {
  id: number;
  title: string;
  style: string;
  answer_mode: string;
  status: string;
  min_questions: number;
  max_questions: number;
  current_turn: number;
  ai_controls_rounds: boolean;
}

export interface ActiveInterview {
  id: number;
  title: string;
  position: string;
  style: string;
  answer_mode: string;
  status: string;
  min_questions: number;
  max_questions: number;
  current_turn: number;
  ai_controls_rounds: boolean;
  created_at: string;
  expires_at: string;
}

export interface InterviewQuestion {
  id: number;
  turn_no: number;
  round_no: number;
  counts_toward_total: boolean;
  category: string;
  competency_code: string;
  question_text: string;
  follow_up_reason: string;
  follow_up_type: string;
  evidence_summary: string;
}

export interface AudioFeatureSummary {
  status: string;
  volume_stability?: number | null;
  pause_ratio?: number | null;
  speech_rate?: number | null;
  pitch_variation?: number | null;
  voiced_ratio?: number | null;
}

export interface RetrievalEvidence {
  doc_id: string;
  role_code: string;
  doc_type: string;
  competency_code: string;
  title: string;
  snippet: string;
  score: number;
}

export interface AnswerEvaluation {
  answer_id: number;
  question_id?: number | null;
  competency_code: string;
  overall_score: number;
  text_scores: Record<string, number>;
  audio_scores: Record<string, number | string | null>;
  explanation: string;
  suggestions: string[];
  evidence: RetrievalEvidence[];
  audio_features: AudioFeatureSummary;
  answer_text?: string;
  asr_text?: string;
}

export interface QuestionPrefetchRequest {
  partial_answer: string;
  partial_answer_version?: number | null;
}

export interface PrefetchCandidate {
  question_text: string;
  follow_up_type: string;
  competency_code: string;
  category: string;
  angle: string;
  confidence: number;
  source: string;
  quality_score?: number | null;
  referenced_facts?: string[];
}

export interface QuestionPrefetch {
  ready: boolean;
  status: string;
  based_on: string;
  suggested_question?: string | null;
  suggested_follow_up_type?: string | null;
  answer_summary?: string;
  buffer_quality?: number | null;
  replacement_happened?: boolean;
  rejected_count?: number;
  candidates: PrefetchCandidate[];
  updated_at?: string | null;
}

export interface InterviewProgress {
  current_round: number;
  min_rounds: number;
  max_rounds: number;
  total_questions_asked: number;
  can_finish_early: boolean;
}

export interface SubmitAnswerResponse {
  answer_id: number;
  evaluation_ready: boolean;
  evaluation?: AnswerEvaluation | null;
  next_action: string;
  next_question: InterviewQuestion | null;
  progress: InterviewProgress;
  report_ready: boolean;
  report_id?: number | null;
  next_question_preview?: string | null;
  next_question_id?: number | null;
}

export interface InterviewNextStep {
  next_action: string;
  next_question: InterviewQuestion | null;
  progress: InterviewProgress;
  report_ready: boolean;
  report_id?: number | null;
  next_question_preview?: string | null;
  next_question_id?: number | null;
}

export interface AnswerEvaluationStatus {
  ready: boolean;
  evaluation?: AnswerEvaluation | null;
}

export interface InterviewDetail {
  session: InterviewSession;
  position: string;
  competencies: CompetencyDimension[];
  resume_summary: ResumeSummary | null;
  questions: InterviewQuestion[];
}

export interface ReportSuggestion {
  issue: string;
  reason: string;
  improvement: string;
  practice_direction: string;
}

export interface InterviewReport {
  session_id: number;
  total_score: number;
  report_level: string;
  competency_scores: Record<string, number>;
  radar: Array<{ name: string; value: number }>;
  suggestions: ReportSuggestion[];
  qa_records: Array<Record<string, unknown>>;
  next_training_plan: string[];
  summary: string;
  voice_scores?: Record<string, number>;
  style?: string | null;
  answer_mode?: string | null;
  analysis_status?: string | null;
  analysis_started_at?: string | null;
  analysis_job_id?: number | null;
  analysis_stage?: string | null;
}

export interface HistoryItem {
  session_id: number;
  title: string;
  position: string;
  style: string;
  answer_mode: string;
  status: string;
  total_score?: number | null;
  report_ready: boolean;
  created_at: string;
  completed_at?: string | null;
}

export interface HistoryQuestionRecord {
  question_id: number;
  answer_id?: number | null;
  turn_no: number;
  round_no: number;
  counts_toward_total: boolean;
  category: string;
  competency_code: string;
  question_text: string;
  follow_up_reason: string;
  follow_up_type: string;
  answer_mode?: string | null;
  audio_path: string;
  audio_duration_seconds?: number | null;
  answer_text: string;
  asr_text: string;
  answered_at?: string | null;
  evaluation_ready: boolean;
  overall_score?: number | null;
  text_scores: Record<string, number>;
  audio_scores: Record<string, number | string | null>;
  audio_features?: AudioFeatureSummary | null;
  explanation: string;
  suggestions: string[];
}

export interface HistoryInterviewDetail extends InterviewReport {
  title: string;
  position: string;
  style: string;
  answer_mode: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  report_ready: boolean;
  questions: HistoryQuestionRecord[];
}

export interface GrowthPoint {
  date: string;
  total_score: number;
}

export interface CompetencyProgress {
  competency: string;
  average_score: number;
  latest_score: number;
  session_count: number;
}

export interface WeaknessInsight {
  tag: string;
  count: number;
  avg_score: number;
}

export interface GrowthSummary {
  completed_sessions: number;
  average_score?: number | null;
  latest_score?: number | null;
  score_delta?: number | null;
  strongest_competency: string;
  focus_competency: string;
  readiness_label: string;
  narrative: string;
  recommendations: string[];
}

export interface GrowthPlanItem {
  title: string;
  focus: string;
  action: string;
  expected_result: string;
}

export interface GrowthInsight {
  summary: GrowthSummary;
  trends: GrowthPoint[];
  competency_progress: CompetencyProgress[];
  weaknesses: WeaknessInsight[];
  plan: GrowthPlanItem[];
}



