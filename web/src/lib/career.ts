import { z } from "zod";

export const timeSlotSchema = z.enum(["morning", "afternoon", "evening", "flexible"]);
export const planTaskTypeSchema = z.enum([
  "question_review",
  "structured_expression",
  "business_sense",
  "mock_interview",
  "resume",
  "application",
]);
export const planItemStatusSchema = z.enum(["pending", "in_progress", "completed", "skipped"]);

export const careerProfileSchema = z.object({
  target_role: z.string(),
  target_level: z.string(),
  target_companies: z.array(z.string()),
  preferred_cities: z.array(z.string()),
  weekly_hours: z.number().int().min(1).max(80),
  available_weekdays: z.array(z.number().int().min(0).max(6)).min(1).max(7),
  preferred_time_slot: timeSlotSchema,
  constraints: z.string(),
  confirmed_at: z.string().nullable(),
  updated_at: z.string().nullable(),
});

export const weeklyPlanItemSchema = z.object({
  id: z.string().uuid(),
  plan_id: z.string().uuid().nullable(),
  scheduled_date: z.iso.date(),
  time_slot: timeSlotSchema,
  scheduled_time: z.string().nullable(),
  estimated_minutes: z.number().int().min(5).max(240),
  task_type: planTaskTypeSchema,
  title: z.string().min(1).max(200),
  reason: z.string().min(1).max(600),
  completion_criteria: z.string().min(1).max(500),
  status: planItemStatusSchema,
  origin: z.enum(["ai", "manual", "migrated"]),
  question_id: z.string().uuid().nullable(),
  question_slug: z.string().nullable(),
  coaching_mode: z.enum(["structured_expression", "business_sense"]).nullable(),
  exercise_type: z.string().nullable(),
  difficulty: z.enum(["guided", "assisted", "pressure"]).nullable(),
  position: z.number().int().min(0).max(100),
  completed_at: z.string().nullable(),
});

export const planningBasisSchema = z.object({
  profile_confirmed: z.boolean(),
  question_count: z.number().int().nonnegative(),
  owned_question_count: z.number().int().nonnegative(),
  due_question_count: z.number().int().nonnegative(),
  recent_training_count: z.number().int().nonnegative(),
  evidence_focus: z.string().nullable(),
});

export const weeklyPlanSchema = z.object({
  id: z.string().uuid(),
  week_start: z.iso.date(),
  goal: z.string(),
  items: z.array(weeklyPlanItemSchema),
  status: z.enum(["active", "completed", "archived"]),
  basis: planningBasisSchema,
  model: z.string().nullable(),
  prompt_version: z.string().nullable(),
  skill_version: z.string().nullable(),
  confirmed_at: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const weeklyPlanDraftSchema = z.object({
  id: z.string().uuid(),
  week_start: z.iso.date(),
  goal: z.string(),
  items: z.array(weeklyPlanItemSchema),
  basis: planningBasisSchema,
  model: z.string(),
  prompt_version: z.string(),
  skill_version: z.string(),
  expires_at: z.string(),
});

export const careerQuestionOptionSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  title: z.string(),
  difficulty: z.string(),
  framework: z.string(),
  topics: z.array(z.string()),
  source_document_name: z.string().nullable(),
  review_due: z.boolean(),
  owned: z.boolean(),
});

export const careerWorkspaceSchema = z.object({
  profile: careerProfileSchema,
  weekly_plan: weeklyPlanSchema.nullable(),
  plan_history: z.array(weeklyPlanSchema),
  question_options: z.array(careerQuestionOptionSchema),
});

export const careerProfileConversationResultSchema = z.object({
  reply: z.string().min(1).max(500),
  profile: careerProfileSchema.nullable(),
});

export const careerProfileRequestSchema = z.object({
  target_role: z.string().max(150).default(""),
  target_level: z.string().max(50).default(""),
  target_companies: z.array(z.string().min(1).max(150)).max(20).default([]),
  preferred_cities: z.array(z.string().min(1).max(100)).max(20).default([]),
  weekly_hours: z.number().int().min(1).max(80).default(5),
  available_weekdays: z.array(z.number().int().min(0).max(6)).min(1).max(7),
  preferred_time_slot: timeSlotSchema,
  constraints: z.string().max(2_000).default(""),
}).strict();

export const weeklyPlanDraftRequestSchema = z.object({
  week_start: z.iso.date(),
  instruction: z.string().max(1_000).default(""),
}).strict();
export const careerProfileMessageRequestSchema = z.object({ message: z.string().trim().min(1).max(1_000) }).strict();
export const weeklyPlanRequestSchema = z.object({
  week_start: z.iso.date(),
  goal: z.string().min(1).max(500),
  items: z.array(weeklyPlanItemSchema).min(1).max(20),
  status: z.enum(["active", "completed", "archived"]).default("active"),
  draft_id: z.string().uuid().optional(),
}).strict();
export const weeklyPlanItemStatusRequestSchema = z.object({ status: planItemStatusSchema }).strict();

export type CareerWorkspace = z.infer<typeof careerWorkspaceSchema>;
export type WeeklyPlan = z.infer<typeof weeklyPlanSchema>;
export type WeeklyPlanDraft = z.infer<typeof weeklyPlanDraftSchema>;
export type WeeklyPlanItem = z.infer<typeof weeklyPlanItemSchema>;
export type CareerQuestionOption = z.infer<typeof careerQuestionOptionSchema>;
export type CareerProfileConversationResult = z.infer<typeof careerProfileConversationResultSchema>;
