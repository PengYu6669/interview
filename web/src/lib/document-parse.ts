import type { components } from "./api-schema";
import { z } from "zod";
import {
  INTERVIEW_TYPE_VALUES,
  type InterviewRound,
  type InterviewType,
  type TargetLevel,
} from "./training-context";

export type ParsedDocument = components["schemas"]["ParsedDocumentResponse"];

export const parsedDocumentSchema: z.ZodType<ParsedDocument> = z.object({
  filename: z.string().min(1),
  media_type: z.string().min(1),
  text: z.string(),
  page_count: z.number().int().nonnegative().nullable(),
  warnings: z.array(z.string()),
});

export interface ReviewMaterial {
  document: ParsedDocument;
  jd: string;
  role: string;
  company: string;
  level: "intern" | "campus" | "mid" | "senior";
  interviewRound: "first" | "second" | "final" | "manager";
  interviewType: InterviewType;
  mode: "relaxed" | "normal" | "stress";
  duration: number;
  pressure: number;
  depth: number;
  guidance: number;
  questionIds: string[];
  questionTitles: string[];
  trainingFocus: string;
  sourceSessionId?: string;
  draftId?: string;
}

export const REVIEW_MATERIAL_STORAGE_KEY = "interview-copilot.review-material.v1";
export const RETRAINING_FOCUS_STORAGE_KEY = "interview-copilot.retraining-focus.v1";

export interface RetrainingContext {
  focus: string;
  source_session_id?: string;
  target_role?: string;
  target_company?: string;
  target_level?: TargetLevel;
  interview_round?: InterviewRound;
  interview_type?: InterviewType;
  mode?: "relaxed" | "normal" | "stress";
  pressure_level?: number;
  depth_level?: number;
  guidance_level?: number;
  improvements: Array<{ skill: string; title: string }>;
}

const retrainingContextSchema: z.ZodType<RetrainingContext> = z.object({
  focus: z.string().trim().min(1).max(500),
  source_session_id: z.string().uuid().optional(),
  target_role: z.string().trim().min(1).max(150).optional(),
  target_company: z.string().trim().max(100).optional(),
  target_level: z.enum(["intern", "campus", "mid", "senior"]).optional(),
  interview_round: z.enum(["first", "second", "final", "manager"]).optional(),
  interview_type: z.enum(INTERVIEW_TYPE_VALUES).optional(),
  mode: z.enum(["relaxed", "normal", "stress"]).optional(),
  pressure_level: z.number().int().min(1).max(5).optional(),
  depth_level: z.number().int().min(1).max(5).optional(),
  guidance_level: z.number().int().min(1).max(5).optional(),
  improvements: z.array(z.object({ skill: z.string().max(80), title: z.string().max(160) })).max(5).default([]),
});

export function readRetrainingContext(raw: string | null): RetrainingContext | null {
  if (!raw) return null;
  try {
    return retrainingContextSchema.parse(JSON.parse(raw));
  } catch {
    const focus = raw.trim().slice(0, 500);
    return focus ? { focus, improvements: [] } : null;
  }
}

export function serializeRetrainingContext(context: RetrainingContext) {
  return JSON.stringify(retrainingContextSchema.parse(context));
}

export const reviewMaterialSchema: z.ZodType<ReviewMaterial> = z.object({
  document: parsedDocumentSchema,
  jd: z.string(),
  role: z.string(),
  company: z.string().max(100).default(""),
  level: z.enum(["intern", "campus", "mid", "senior"]).default("campus"),
  interviewRound: z.enum(["first", "second", "final", "manager"]).default("first"),
  interviewType: z.enum(INTERVIEW_TYPE_VALUES).default("comprehensive"),
  mode: z.enum(["relaxed", "normal", "stress"]).default("normal"),
  duration: z.number().int().min(1).max(180).default(30),
  pressure: z.number().int().min(1).max(5).default(3),
  depth: z.number().int().min(1).max(5).default(4),
  guidance: z.number().int().min(1).max(5).default(3),
  questionIds: z.array(z.string().uuid()).max(20).default([]),
  questionTitles: z.array(z.string()).max(20).default([]),
  trainingFocus: z.string().max(500).default(""),
  sourceSessionId: z.string().uuid().optional(),
  draftId: z.string().uuid().optional(),
});
