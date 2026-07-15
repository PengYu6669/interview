import type { components } from "./api-schema";
import { z } from "zod";

export type QuestionSummary = components["schemas"]["QuestionSummary"];
export type QuestionDetail = components["schemas"]["QuestionDetail"];
export type UserQuestionState = components["schemas"]["UserQuestionState"];
export type QuestionImportResult = components["schemas"]["QuestionImportResult"];
export type QuestionChatAnswer = components["schemas"]["QuestionChatAnswer"];
export type QuestionChatHistory = components["schemas"]["QuestionChatHistory"];
export type QuestionChatMessageData = components["schemas"]["QuestionChatMessageData"];

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
});
export const questionSummarySchema: z.ZodType<QuestionSummary> = questionSummaryObjectSchema;

export const questionDetailSchema: z.ZodType<QuestionDetail> = questionSummaryObjectSchema.extend({
  intent: z.string(),
  answer_outline: z.array(z.string()),
  common_mistakes: z.array(z.string()),
  sources: z.array(z.object({ title: z.string(), url: z.string(), publisher: z.string() })),
  content_markdown: z.string(),
  editable: z.boolean(),
  source_document_name: z.string().nullable(),
});

export const questionImportResultSchema: z.ZodType<QuestionImportResult> = z.object({
  questions: z.array(questionDetailSchema),
  warnings: z.array(z.string()),
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
