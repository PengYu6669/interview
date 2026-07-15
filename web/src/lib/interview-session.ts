import type { components } from "./api-schema";
import { z } from "zod";

export type InterviewSessionData = components["schemas"]["InterviewSessionData"];
export type InterviewRuntimeData = components["schemas"]["InterviewRuntimeData"];

export const interviewSessionSchema: z.ZodType<InterviewSessionData> = z.object({
  id: z.string().uuid(),
  draft_id: z.string().uuid(),
  status: z.string(),
  target_role: z.string(),
  target_company: z.string(),
  target_level: z.enum(["intern", "campus", "mid", "senior"]),
  interview_round: z.enum(["first", "second", "final", "manager"]),
  interview_type: z.enum(["comprehensive", "project", "technical", "system_design", "coding", "behavioral", "weak_area"]),
  mode: z.string(),
  duration_minutes: z.number().int(),
  pressure_level: z.number().int().min(1).max(5),
  depth_level: z.number().int().min(1).max(5),
  guidance_level: z.number().int().min(1).max(5),
  training_focus: z.string(),
  summary: z.string(),
  phases: z.array(z.object({
    name: z.string(),
    kind: z.enum(["warmup", "project", "technical", "system_design", "coding", "behavioral", "candidate_qa"]),
    minutes: z.number().int(),
    skills: z.array(z.string()),
    question_count: z.number().int(),
  })),
  model: z.string(),
  prompt_version: z.string(),
  created_at: z.string(),
});

export const interviewRuntimeSchema: z.ZodType<InterviewRuntimeData> = z.object({
  id: z.string().uuid(),
  status: z.string(),
  target_role: z.string(),
  target_company: z.string(),
  target_level: z.enum(["intern", "campus", "mid", "senior"]),
  interview_round: z.enum(["first", "second", "final", "manager"]),
  interview_type: z.enum(["comprehensive", "project", "technical", "system_design", "coding", "behavioral", "weak_area"]),
  mode: z.string(),
  duration_minutes: z.number().int(),
  pressure_level: z.number().int().min(1).max(5),
  depth_level: z.number().int().min(1).max(5),
  guidance_level: z.number().int().min(1).max(5),
  training_focus: z.string(),
  phases: z.array(z.object({
    name: z.string(),
    kind: z.enum(["warmup", "project", "technical", "system_design", "coding", "behavioral", "candidate_qa"]),
    minutes: z.number().int(),
    skills: z.array(z.string()),
    question_count: z.number().int(),
  })),
  current_phase_index: z.number().int(),
  current_question_index: z.number().int(),
  current_question: z.string().nullable(),
  current_question_number: z.number().int().positive(),
  current_question_kind: z.enum(["main", "follow_up"]),
  follow_up_count: z.number().int().nonnegative(),
  interviewer_transition: z.string().nullable(),
  interviewer_reply: z.string().nullable(),
  closing_statement: z.string().nullable(),
  opening_statement: z.string(),
  answered_questions: z.number().int(),
  total_questions: z.number().int(),
  started_at: z.string(),
  remaining_seconds: z.number().int().nonnegative(),
});

export const INTERVIEW_SESSION_STORAGE_KEY = "interview-copilot.interview-session.v1";
