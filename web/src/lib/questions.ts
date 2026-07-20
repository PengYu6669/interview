import type { components } from "./api-schema";
import { z } from "zod";

export type QuestionSummary = components["schemas"]["QuestionSummary"];
export type QuestionDetail = components["schemas"]["QuestionDetail"];
export type UserQuestionState = components["schemas"]["UserQuestionState"];
export type QuestionDocumentSummary = components["schemas"]["QuestionDocumentSummary"];
export type QuestionChatAnswer = components["schemas"]["QuestionChatAnswer"];
export type QuestionChatHistory = components["schemas"]["QuestionChatHistory"];
export type QuestionChatMessageData = components["schemas"]["QuestionChatMessageData"];

export const questionSetSummarySchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  kind: z.string(),
  status: z.string(),
  target_count: z.number().int().nonnegative(),
  question_count: z.number().int().nonnegative(),
  document_id: z.string().uuid().nullable(),
  document_name: z.string().nullable(),
  knowledge_point_count: z.number().int().nonnegative(),
  covered_knowledge_point_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const questionSetDetailSchema = questionSetSummarySchema.extend({
  questions: z.array(z.lazy(() => questionSummaryObjectSchema)),
});
export type QuestionSetSummary = z.infer<typeof questionSetSummarySchema>;
export type QuestionSetDetail = z.infer<typeof questionSetDetailSchema>;

const topicSchema = z.object({ id: z.string().uuid(), slug: z.string(), name: z.string() });
const citationSchema = z.object({ index: z.number().int().positive(), title: z.string(), url: z.string().nullable(), quote: z.string() });

const questionSummaryObjectSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  title: z.string(),
  prompt: z.string(),
  difficulty: z.string(),
  question_type: z.string(),
  topics: z.array(topicSchema),
  framework: z.string(),
  source_document_id: z.string().uuid().nullable(),
  source_document_name: z.string().nullable(),
  source_document_version: z.number().int().nullable(),
});
export const questionSummarySchema: z.ZodType<QuestionSummary> = questionSummaryObjectSchema;

export const questionDetailSchema: z.ZodType<QuestionDetail> = questionSummaryObjectSchema.extend({
  intent: z.string(),
  answer_outline: z.array(z.string()),
  common_mistakes: z.array(z.string()),
  sources: z.array(z.object({ title: z.string(), url: z.string(), publisher: z.string() })),
  content_markdown: z.string(),
  editable: z.boolean(),
  evidence: z.array(z.object({ section_key: z.string(), heading_path: z.array(z.string()), quote: z.string() })),
});

export const questionDocumentSchema: z.ZodType<QuestionDocumentSummary> = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  media_type: z.string(),
  version: z.number().int().positive(),
  status: z.string(),
  warnings: z.array(z.string()),
  coverage_ratio: z.number().min(0).max(1),
  section_count: z.number().int().nonnegative(),
  covered_section_count: z.number().int().nonnegative(),
  question_count: z.number().int().nonnegative(),
  knowledge_point_count: z.number().int().nonnegative(),
  covered_knowledge_point_count: z.number().int().nonnegative(),
  suggested_question_count: z.number().int().min(0).max(100),
  requested_question_limit: z.number().int().min(10).max(100),
  created_at: z.string(),
  updated_at: z.string(),
});

export const questionChatAnswerSchema: z.ZodType<QuestionChatAnswer> = z.object({
  answer_markdown: z.string(),
  citations: z.array(citationSchema),
  conversation_id: z.string().uuid(),
});

export const questionChatHistorySchema: z.ZodType<QuestionChatHistory> = z.object({
  conversation_id: z.string().uuid(),
  messages: z.array(z.object({
    role: z.enum(["user", "assistant"]),
    content: z.string(),
    citations: z.array(citationSchema),
    created_at: z.string(),
  })),
});

export const userQuestionStateSchema: z.ZodType<UserQuestionState> = z.object({
  status: z.string(),
  bookmarked: z.boolean(),
  note: z.string(),
  review_interval_days: z.number().int().nonnegative(),
  review_streak: z.number().int().nonnegative(),
  last_reviewed_at: z.string().nullable(),
  review_due_at: z.string().nullable(),
});

export const QUESTION_INTERVIEW_SELECTION_KEY = "interview-copilot.question-selection.v1";
export const QUESTION_COACHING_SELECTION_KEY = "interview-copilot.coaching-question-selection.v1";
