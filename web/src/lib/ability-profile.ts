import type { components } from "./api-schema";
import { z } from "zod";

export type AbilityProfileData = components["schemas"]["AbilityProfileData"];

export const abilityProfileSchema: z.ZodType<AbilityProfileData> = z.object({
  report_count: z.number().int().nonnegative(),
  average_score: z.number().int().nullable(),
  average_coverage: z.number().int().nullable(),
  kline: z.array(z.object({
    session_id: z.string().uuid(),
    date: z.string(),
    open: z.number().int(),
    high: z.number().int(),
    low: z.number().int(),
    close: z.number().int(),
    evidence_coverage: z.number().int(),
    confidence: z.number(),
  })),
  skills: z.array(z.object({
    skill: z.string(),
    score: z.number().int(),
    confidence: z.number(),
    evidence_count: z.number().int(),
    report_count: z.number().int(),
    trend: z.number().int(),
    source_session_id: z.string().uuid(),
    training_focus: z.string(),
  })),
  next_training: z.string().nullable(),
  coaching: z.object({
    session_count: z.number().int().nonnegative(),
    completed_count: z.number().int().nonnegative(),
    skills: z.array(z.object({
      dimension: z.string(),
      mode: z.enum(["structured_expression", "business_sense"]),
      score: z.number().int().min(0).max(100),
      confidence: z.number().min(0).max(1),
      evidence_count: z.number().int().positive(),
      session_count: z.number().int().positive(),
      source_session_id: z.string().uuid(),
      latest_feedback: z.string(),
      trend: z.number().int().min(-100).max(100),
      mastery_status: z.enum(["practice", "improving", "stable"]),
    })),
    next_mode: z.enum(["structured_expression", "business_sense"]).nullable(),
    next_focus: z.string().nullable(),
    current_streak_days: z.number().int().nonnegative(),
    next_difficulty: z.enum(["guided", "assisted", "pressure"]),
  }),
});
