import type { components } from "./api-schema";
import { z } from "zod";

import { authUserSchema } from "./auth";

export type AccountDataSummary = components["schemas"]["AccountDataSummary"];

export const accountDataSummarySchema: z.ZodType<AccountDataSummary> = z.object({
  account: authUserSchema,
  draft_count: z.number().int().nonnegative(),
  interview_count: z.number().int().nonnegative(),
  report_count: z.number().int().nonnegative(),
  private_question_count: z.number().int().nonnegative(),
  note_count: z.number().int().nonnegative(),
});

export const deleteAccountRequestSchema = z.object({
  current_password: z.string().min(1, "请输入当前密码").max(128, "密码过长"),
});
