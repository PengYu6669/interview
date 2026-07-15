import type { components } from "./api-schema";
import { z } from "zod";

export type AuthUser = components["schemas"]["UserProfile"];

export const authUserSchema: z.ZodType<AuthUser> = z.object({
  id: z.string().uuid(),
  username: z.string().min(1),
  email: z.string().min(1),
  created_at: z.string().min(1),
});

export const authResultSchema = z.object({
  user: authUserSchema,
  session_token: z.string().min(20),
  expires_at: z.string().datetime(),
});

export const AUTH_COOKIE_NAME = "interview_session";
