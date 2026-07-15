import { z } from "zod";

import type { InterviewRuntimeData } from "@/lib/interview-session";

const answerDraftSchema = z.object({
  session_id: z.string().uuid(),
  question_number: z.number().int().positive(),
  question_kind: z.enum(["main", "follow_up"]),
  question: z.string().min(1),
  answer: z.string().min(1).max(20_000),
  answer_mode: z.enum(["text", "voice"]),
  client_message_id: z.string().uuid().nullable(),
  updated_at: z.string().datetime(),
});

export type PendingAnswerDraft = z.infer<typeof answerDraftSchema>;

function storageKey(sessionId: string) {
  return `interview-copilot.pending-answer.${sessionId}.v1`;
}

export function readAnswerDraft(sessionId: string): PendingAnswerDraft | null {
  const raw = sessionStorage.getItem(storageKey(sessionId));
  if (!raw) return null;
  try {
    return answerDraftSchema.parse(JSON.parse(raw));
  } catch {
    sessionStorage.removeItem(storageKey(sessionId));
    return null;
  }
}

export function writeAnswerDraft(draft: PendingAnswerDraft) {
  sessionStorage.setItem(storageKey(draft.session_id), JSON.stringify(draft));
}

export function clearAnswerDraft(sessionId: string) {
  sessionStorage.removeItem(storageKey(sessionId));
}

export function draftMatchesRuntime(
  draft: PendingAnswerDraft,
  runtime: InterviewRuntimeData,
) {
  return draft.session_id === runtime.id
    && draft.question_number === runtime.current_question_number
    && draft.question_kind === runtime.current_question_kind
    && draft.question === runtime.current_question;
}
