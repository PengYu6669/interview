import { z } from "zod";

export const aiJobStatusSchema = z.object({
  id: z.string().uuid(),
  kind: z.enum(["question_import", "career_plan"]),
  status: z.enum(["queued", "processing", "completed", "failed"]),
  stage: z.string(),
  progress: z.number().int().min(0).max(100),
  estimated_seconds: z.number().int().nonnegative(),
  resource_id: z.string().uuid().nullable(),
  error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  completed_at: z.string().nullable(),
});

export type AiJobStatus = z.infer<typeof aiJobStatusSchema>;

export function remainingSeconds(job: AiJobStatus, elapsedSeconds: number) {
  if (job.progress > 5) {
    const projectedTotal = elapsedSeconds / (job.progress / 100);
    return Math.max(0, Math.round(projectedTotal - elapsedSeconds));
  }
  return Math.max(0, Math.round(job.estimated_seconds - elapsedSeconds));
}
