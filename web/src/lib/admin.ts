import { z } from "zod";

export const adminUserSchema = z.object({
  id: z.string().uuid(),
  username: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["user", "admin"]),
  created_at: z.string().datetime(),
});

export const adminUserMetricsSchema = z.object({
  total_users: z.number().int().nonnegative(),
  daily_active_users: z.number().int().nonnegative(),
  weekly_active_users: z.number().int().nonnegative(),
  new_users_today: z.number().int().nonnegative(),
  admin_users: z.number().int().nonnegative(),
  timezone: z.literal("Asia/Shanghai"),
});

export const adminUserListSchema = z.object({
  metrics: adminUserMetricsSchema,
  users: adminUserSchema.array(),
});

export const adminLogSchema = z.object({
  id: z.string().uuid(),
  request_id: z.string().uuid(),
  session_id: z.string().uuid().nullable(),
  tool_name: z.string().min(1),
  succeeded: z.boolean(),
  duration_ms: z.number().int().nonnegative(),
  error_type: z.string().nullable(),
  created_at: z.string().datetime(),
});

export const adminLogListSchema = adminLogSchema.array();

export type AdminUser = z.infer<typeof adminUserSchema>;
export type AdminUserMetrics = z.infer<typeof adminUserMetricsSchema>;
export type AdminLog = z.infer<typeof adminLogSchema>;
