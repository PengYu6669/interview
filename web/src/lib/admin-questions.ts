import { z } from "zod";

export const adminQuestionSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  title: z.string(),
  prompt: z.string(),
  difficulty: z.string(),
  question_type: z.string(),
  topics: z.array(z.object({ id: z.string().uuid(), slug: z.string(), name: z.string() })),
  framework: z.string(),
  source_document_id: z.string().uuid().nullable(),
  source_document_name: z.string().nullable(),
  source_document_version: z.number().int().nullable(),
  published: z.boolean(),
  owner_user_id: z.string().uuid().nullable(),
  evidence_count: z.number().int().nonnegative(),
  created_at: z.string(),
});

export const adminQuestionListSchema = adminQuestionSchema.array();
export const adminQuestionDetailSchema = adminQuestionSchema.extend({
  intent: z.string(),
  answer_outline: z.array(z.string()),
  common_mistakes: z.array(z.string()),
  content_markdown: z.string(),
  evidence: z.array(z.object({
    section_key: z.string(),
    heading_path: z.array(z.string()),
    quote: z.string(),
  })),
});
export type AdminQuestion = z.infer<typeof adminQuestionSchema>;
export type AdminQuestionDetail = z.infer<typeof adminQuestionDetailSchema>;
