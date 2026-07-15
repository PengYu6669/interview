import type { components } from "./api-schema";
import { boardStateSchema } from "./interview-board";
import { z } from "zod";

export type InterviewHistoryItem = components["schemas"]["InterviewHistoryItem"];
export type InterviewReportData = components["schemas"]["InterviewReportData"];
export type InterviewReportGenerationData = components["schemas"]["InterviewReportGenerationData"];
export type InterviewReportReviewData = components["schemas"]["InterviewReportReviewData"];
export type InterviewReportReviewRequest = components["schemas"]["InterviewReportReviewRequest"];

export const interviewHistorySchema: z.ZodType<InterviewHistoryItem[]> = z.array(z.object({
  id: z.string().uuid(),
  status: z.string(),
  target_role: z.string(),
  target_company: z.string(),
  target_level: z.enum(["intern", "campus", "mid", "senior"]),
  interview_round: z.enum(["first", "second", "final", "manager"]),
  interview_type: z.enum(["comprehensive", "project", "technical", "system_design", "behavioral", "weak_area"]),
  mode: z.string(),
  duration_minutes: z.number().int(),
  pressure_level: z.number().int(),
  depth_level: z.number().int(),
  guidance_level: z.number().int(),
  answered_questions: z.number().int(),
  total_questions: z.number().int(),
  turn_count: z.number().int(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  report_available: z.boolean(),
  report_status: z.enum(["not_started", "generating", "ready", "failed"]),
}));

export const interviewReportGenerationSchema: z.ZodType<InterviewReportGenerationData> = z.object({
  session_id: z.string().uuid(),
  status: z.enum(["not_started", "generating", "ready", "failed"]),
  message: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

const findingSchema = z.object({
  skill: z.string(),
  title: z.string(),
  evidence_turns: z.array(z.number().int()),
  evidence_quote: z.string(),
  analysis: z.string(),
  improvement: z.string().nullable(),
});

const verificationCitationSchema = z.object({
  chunk_id: z.string().uuid(),
  title: z.string(),
  quote: z.string(),
  version: z.string().nullable().optional(),
  source_urls: z.array(z.string()).optional(),
});

const verifiedClaimSchema = z.object({
  sequence: z.number().int().positive(),
  claim: z.string(),
  evidence_quote: z.string(),
  result: z.enum(["supported", "contradicted", "uncertain"]),
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
  citations: z.array(verificationCitationSchema).optional(),
});

export const interviewReportReviewRequestSchema: z.ZodType<InterviewReportReviewRequest> = z.object({
  client_request_id: z.string().uuid(),
  skill_index: z.number().int().min(0).max(11),
  action: z.enum(["reevaluate", "exclude"]),
  reason: z.string().trim().min(10).max(1_000),
});

export const interviewReportReviewSchema: z.ZodType<InterviewReportReviewData> = z.object({
  id: z.string().uuid(),
  session_id: z.string().uuid(),
  skill_index: z.number().int().nonnegative(),
  skill: z.string(),
  original_score: z.number().int().min(0).max(100),
  action: z.enum(["reevaluate", "exclude"]),
  reason: z.string(),
  status: z.enum(["pending", "resolved", "failed"]),
  decision: z.enum(["upheld", "revised", "uncertain", "excluded"]).nullable(),
  rationale: z.string().nullable(),
  revised_score: z.number().int().min(0).max(100).nullable().optional(),
  confidence: z.number().min(0).max(1).nullable().optional(),
  model: z.string().nullable(),
  prompt_version: z.string().nullable(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
});

export const interviewReportSchema: z.ZodType<InterviewReportData> = z.object({
  session_id: z.string().uuid(),
  target_role: z.string(),
  target_company: z.string(),
  target_level: z.enum(["intern", "campus", "mid", "senior"]),
  interview_round: z.enum(["first", "second", "final", "manager"]),
  interview_type: z.enum(["comprehensive", "project", "technical", "system_design", "behavioral", "weak_area"]),
  mode: z.string(),
  pressure_level: z.number().int().min(1).max(5),
  depth_level: z.number().int().min(1).max(5),
  guidance_level: z.number().int().min(1).max(5),
  session_status: z.string(),
  duration_minutes: z.number().int(),
  turn_count: z.number().int(),
  turns: z.array(z.object({
    sequence: z.number().int().positive(),
    phase_index: z.number().int().nonnegative(),
    phase_name: z.string(),
    question_index: z.number().int().nonnegative(),
    question_number: z.number().int().positive(),
    question: z.string(),
    answer: z.string(),
    answer_mode: z.string(),
    decision: z.string(),
    transition: z.string(),
    interviewer_reply: z.string().nullable(),
    follow_up_question: z.string().nullable(),
    created_at: z.string(),
  })),
  board_snapshot: z.object({ revision: z.number().int().nonnegative(), state: boardStateSchema, created_at: z.string() }).nullable().optional(),
  content: z.object({
    overall_score: z.number().int(),
    evidence_coverage: z.number().int(),
    confidence: z.number(),
    summary: z.string(),
    strengths: z.array(findingSchema),
    improvements: z.array(findingSchema),
    skill_scores: z.array(z.object({ skill: z.string(), score: z.number().int(), confidence: z.number(), evidence_turns: z.array(z.number().int()) })),
    next_training: z.string(),
  }),
  reviews: z.array(interviewReportReviewSchema),
  verification_status: z.enum(["completed", "degraded", "not_run"]),
  verification_error: z.string().nullable(),
  verified_claims: z.array(verifiedClaimSchema),
  model: z.string(),
  prompt_version: z.string(),
  rubric_version: z.string(),
  created_at: z.string(),
});
