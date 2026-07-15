import { z } from "zod";

import type { components } from "./api-schema";

export type CareerWorkspace = components["schemas"]["CareerWorkspace"];
export type WeeklyPlanItem = components["schemas"]["WeeklyPlanItem"];

const profileSchema = z.object({
  target_role: z.string(),
  target_level: z.string(),
  target_companies: z.array(z.string()),
  preferred_cities: z.array(z.string()),
  weekly_hours: z.number().int().min(1).max(80),
  constraints: z.string(),
  confirmed_at: z.string().nullable(),
  updated_at: z.string().nullable(),
});

const itemSchema = z.object({
  id: z.string().uuid(),
  category: z.enum(["learning", "interview", "resume", "application"]),
  title: z.string(),
  target_count: z.number().int().positive(),
  completed_count: z.number().int().nonnegative(),
});

export const careerWorkspaceSchema: z.ZodType<CareerWorkspace> = z.object({
  profile: profileSchema,
  weekly_plan: z.object({
    id: z.string().uuid(),
    week_start: z.string(),
    goal: z.string(),
    items: z.array(itemSchema),
    status: z.enum(["active", "completed", "archived"]),
    created_at: z.string(),
    updated_at: z.string(),
  }).nullable(),
  suggested_focus: z.string().nullable(),
});
