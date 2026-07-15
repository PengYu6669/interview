import { z } from "zod";

import type { components } from "./api-schema";

export type CareerWorkspace = components["schemas"]["CareerWorkspace"];
export type WeeklyPlanItem = components["schemas"]["WeeklyPlanItem"];

export const careerProfileSchema = z.object({
  target_role: z.string(),
  target_level: z.string(),
  target_companies: z.array(z.string()),
  preferred_cities: z.array(z.string()),
  weekly_hours: z.number().int().min(1).max(80),
  constraints: z.string(),
  confirmed_at: z.string().nullable(),
  updated_at: z.string().nullable(),
});

export const weeklyPlanItemSchema = z.object({
  id: z.string().uuid(),
  category: z.enum(["learning", "interview", "resume", "application"]),
  title: z.string(),
  target_count: z.number().int().positive(),
  completed_count: z.number().int().nonnegative(),
});

export const weeklyPlanSchema = z.object({
    id: z.string().uuid(),
    week_start: z.string(),
    goal: z.string(),
    items: z.array(weeklyPlanItemSchema),
    status: z.enum(["active", "completed", "archived"]),
    created_at: z.string(),
    updated_at: z.string(),
});

export const careerWorkspaceSchema: z.ZodType<CareerWorkspace> = z.object({
  profile: careerProfileSchema,
  weekly_plan: weeklyPlanSchema.nullable(),
  suggested_focus: z.string().nullable(),
});

export const careerProfileRequestSchema = z.object({
  target_role: z.string().max(150).default(""),
  target_level: z.string().max(50).default(""),
  target_companies: z.array(z.string().min(1).max(150)).max(20).default([]),
  preferred_cities: z.array(z.string().min(1).max(100)).max(20).default([]),
  weekly_hours: z.number().int().min(1).max(80).default(5),
  constraints: z.string().max(2_000).default(""),
}).strict();

export const weeklyPlanRequestSchema = z.object({
  week_start: z.iso.date(),
  goal: z.string().min(1).max(500),
  items: z.array(weeklyPlanItemSchema.extend({
    title: z.string().min(1).max(200),
    target_count: z.number().int().min(1).max(100),
    completed_count: z.number().int().min(0).max(100),
  }).refine((item) => item.completed_count <= item.target_count, {
    message: "完成数量不能超过目标数量",
  })).min(1).max(20),
  status: z.enum(["active", "completed", "archived"]).default("active"),
}).strict();
