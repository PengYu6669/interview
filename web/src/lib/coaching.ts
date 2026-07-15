import { z } from "zod";

import type { components } from "./api-schema";

export type CoachingSession = components["schemas"]["CoachingSessionData"];
export type CoachingSummary = components["schemas"]["CoachingSessionSummary"];
export type CoachingMode = CoachingSession["mode"];

const assessmentSchema = z.object({
  key: z.string(),
  status: z.enum(["observed", "evidence_insufficient"]),
  level: z.number().int().min(1).max(5).nullable(),
  evidence_quote: z.string().nullable(),
  feedback: z.string(),
  confidence: z.number().min(0).max(1),
});

const taskSchema = z.object({
  title: z.string(),
  objective: z.string(),
  scenario: z.string(),
  primary_question: z.string(),
  estimated_minutes: z.number().int(),
  dimensions: z.array(z.string()),
});

const decisionSchema = z.object({
  action: z.enum(["follow_up", "retry", "complete"]),
  coach_reply: z.string(),
  next_question: z.string().nullable().optional(),
  assessments: z.array(assessmentSchema),
  summary: z.string(),
});

export const coachingSessionSchema: z.ZodType<CoachingSession> = z.object({
  id: z.string().uuid(),
  mode: z.enum(["structured_expression", "business_sense"]),
  channel: z.enum(["text", "voice"]),
  status: z.enum(["planned", "active", "completed"]),
  target_role: z.string(),
  training_goal: z.string(),
  skill_name: z.string(),
  skill_version: z.string(),
  task: taskSchema,
  current_question: z.string().nullable(),
  turns: z.array(z.object({
    id: z.string().uuid(),
    sequence: z.number().int(),
    answer: z.string(),
    answer_mode: z.enum(["text", "voice"]),
    decision: decisionSchema,
    created_at: z.string(),
  })),
  created_at: z.string(),
  updated_at: z.string(),
  completed_at: z.string().nullable(),
});

export const coachingSummarySchema: z.ZodType<CoachingSummary[]> = z.array(z.object({
  id: z.string().uuid(),
  mode: z.enum(["structured_expression", "business_sense"]),
  channel: z.enum(["text", "voice"]),
  status: z.enum(["planned", "active", "completed"]),
  title: z.string(),
  target_role: z.string(),
  current_question: z.string().nullable(),
  turn_count: z.number().int(),
  updated_at: z.string(),
}));

export const COACHING_MODE_LABELS: Record<CoachingMode, string> = {
  structured_expression: "结构化表达",
  business_sense: "业务 Sense",
};

export const COACHING_DIMENSION_LABELS: Record<string, string> = {
  conclusion: "结论先行",
  context: "背景控制",
  ownership: "个人职责",
  actions: "行动细节",
  tradeoffs: "方案取舍",
  results: "量化结果",
  reflection: "复盘改进",
  user_problem: "用户问题",
  business_goal: "业务目标",
  metrics: "指标设计",
  prioritization: "方案优先级",
  economics: "成本收益",
  risk: "风险控制",
  validation: "验证复盘",
};
