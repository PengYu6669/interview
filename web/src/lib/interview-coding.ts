import { z } from "zod";

const testCaseSchema = z.object({
  name: z.string(),
  arguments: z.array(z.json()),
  expected: z.json(),
});

export const codingProblemSchema = z.object({
  title: z.string(),
  description: z.string(),
  language: z.literal("python"),
  entrypoint: z.literal("solve"),
  starter_code: z.string(),
  constraints: z.array(z.string()),
  public_tests: z.array(testCaseSchema),
});

export const codingSnapshotSchema = z.object({
  id: z.string().uuid(),
  session_id: z.string().uuid(),
  phase_index: z.number().int().nonnegative(),
  question_index: z.number().int().nonnegative(),
  revision: z.number().int().nonnegative(),
  client_snapshot_id: z.string().uuid(),
  source: z.string(),
  complexity_notes: z.string(),
  created_at: z.string(),
});

export const codingWorkspaceSchema = z.object({
  problem: codingProblemSchema,
  snapshot: codingSnapshotSchema.nullable(),
});

const testResultSchema = z.object({
  name: z.string(),
  passed: z.boolean(),
  expected: z.json(),
  actual: z.union([z.json(), z.string()]).nullable(),
  error: z.string().nullable(),
  stdout: z.string(),
  duration_ms: z.number().int().nonnegative(),
});

export const codingRunSchema = z.object({
  id: z.string().uuid(),
  session_id: z.string().uuid(),
  snapshot_id: z.string().uuid(),
  client_request_id: z.string().uuid(),
  status: z.enum(["passed", "failed", "compile_error", "runtime_error", "timed_out", "output_limit", "memory_limit"]),
  tests: z.array(testResultSchema),
  duration_ms: z.number().int().nonnegative(),
  error: z.string().nullable(),
  created_at: z.string(),
});

export type CodingWorkspace = z.infer<typeof codingWorkspaceSchema>;
export type CodingRun = z.infer<typeof codingRunSchema>;
