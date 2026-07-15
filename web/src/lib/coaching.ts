import { z } from "zod";

import type { components } from "./api-schema";

export type CoachingSession = components["schemas"]["CoachingSessionData"];
export type CoachingSummary = components["schemas"]["CoachingSessionSummary"];
export type CoachingMode = CoachingSession["mode"];
export type CoachingExerciseType = CoachingSession["task"]["exercise_type"];
export type CoachingDifficulty = CoachingSession["task"]["difficulty"];

const difficultySchema = z.enum(["guided", "assisted", "pressure"]);
const exerciseTypeSchema = z.enum(["star_story", "prep_pitch", "structure_puzzle", "decision_simulation", "fermi_estimation"]);

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
  exercise_type: exerciseTypeSchema,
  framework: z.enum(["star", "prep", "business_decision", "fermi"]),
  difficulty: difficultySchema,
  time_limit_seconds: z.number().int().min(60).max(900),
  target_dimension: z.string(),
  scaffold: z.array(z.object({ key: z.string(), label: z.string(), prompt: z.string() })),
  puzzle: z.object({
    instruction: z.string(),
    fragments: z.array(z.object({ id: z.string(), text: z.string(), target_key: z.string(), distractor: z.boolean() })),
  }).nullable(),
  scenario_version: z.string(),
  facts: z.array(z.object({ label: z.string(), value: z.string(), source_type: z.enum(["virtual", "curated"]), source_label: z.string().nullable() })),
  constraint_change: z.string().nullable(),
  source_questions: z.array(z.object({
    id: z.string().uuid(),
    title: z.string(),
    prompt: z.string(),
    framework: z.enum(["technical", "star", "prep", "system_design"]),
    evidence_quotes: z.array(z.string()).optional(),
  })).optional(),
});

const decisionSchema = z.object({
  action: z.enum(["follow_up", "retry", "complete"]),
  coach_reply: z.string(),
  next_question: z.string().nullable().optional(),
  assessments: z.array(assessmentSchema),
  summary: z.string(),
  evidence_segments: z.array(z.object({ key: z.string(), label: z.string(), evidence_quote: z.string() })),
  priority_gaps: z.array(z.object({ dimension: z.string(), diagnosis: z.string(), retry_prompt: z.string() })),
  comparison: z.object({
    items: z.array(z.object({
      dimension: z.string(),
      change: z.enum(["improved", "stable", "regressed", "insufficient"]),
      before_level: z.number().int().min(1).max(5).nullable(),
      after_level: z.number().int().min(1).max(5).nullable(),
      before_quote: z.string().nullable(),
      after_quote: z.string().nullable(),
      explanation: z.string(),
    })),
    overall_summary: z.string(),
  }).nullable(),
  next_practice: z.object({ focus: z.string(), recommended_difficulty: difficultySchema, estimated_minutes: z.number().int() }).nullable(),
  delivery_metrics: z.object({
    source: z.enum(["voice_transcript", "text"]),
    character_count: z.number().int().nonnegative(),
    characters_per_minute: z.number().int().nonnegative().nullable(),
    filler_counts: z.record(z.string(), z.number().int().nonnegative()),
    filler_total: z.number().int().nonnegative(),
  }).nullable(),
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
    attempt_number: z.number().int().min(1).max(3),
    elapsed_seconds: z.number().int().min(0).max(3_600).nullable(),
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
  exercise_type: exerciseTypeSchema,
  difficulty: difficultySchema,
  updated_at: z.string(),
}));

export const COACHING_MODE_LABELS: Record<CoachingMode, string> = {
  structured_expression: "结构化表达",
  business_sense: "业务 Sense",
};

export const COACHING_EXERCISE_LABELS: Record<CoachingExerciseType, string> = {
  star_story: "STAR 故事",
  prep_pitch: "PREP 观点",
  structure_puzzle: "结构拼装",
  decision_simulation: "决策推演",
  fermi_estimation: "费米估算",
};

export const COACHING_DIFFICULTY_LABELS: Record<CoachingDifficulty, string> = {
  guided: "有骨架",
  assisted: "关键词提示",
  pressure: "限时脱稿",
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
  assumptions: "关键假设",
  prioritization: "方案优先级",
  economics: "成本收益",
  risk: "风险控制",
  validation: "验证复盘",
};
