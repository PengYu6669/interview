import { z } from "zod";

import { INTERVIEW_TYPE_VALUES } from "./training-context";

export const trainingDraftSummarySchema = z.object({
  id: z.string().uuid(),
  resume_filename: z.string().min(1).max(255),
  target_role: z.string().max(150),
  target_company: z.string().max(100),
  interview_type: z.enum(INTERVIEW_TYPE_VALUES),
  updated_at: z.string(),
  expires_at: z.string(),
});

export const trainingDraftSchema = trainingDraftSummarySchema.extend({
  resume_text: z.string().max(80_000),
  jd: z.string().max(30_000),
  target_level: z.enum(["intern", "campus", "mid", "senior"]),
  interview_round: z.enum(["first", "second", "final", "manager"]),
  mode: z.enum(["relaxed", "normal", "stress"]),
  duration_minutes: z.number().int().min(1).max(180),
  pressure_level: z.number().int().min(1).max(5),
  depth_level: z.number().int().min(1).max(5),
  guidance_level: z.number().int().min(1).max(5),
  question_ids: z.array(z.string().uuid()).max(20),
  training_focus: z.string().max(500),
  source_session_id: z.string().uuid().nullable(),
  career_plan_item_id: z.string().uuid().nullable(),
  created_at: z.string(),
  extraction: z.unknown().nullable(),
});

export type TrainingDraft = z.infer<typeof trainingDraftSchema>;
export type TrainingDraftSummary = z.infer<typeof trainingDraftSummarySchema>;
