import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const schema = z.object({
  client_message_id: z.string().uuid(),
  answer: z.string().min(1).max(20_000),
  answer_mode: z.enum(["text", "voice"]),
  elapsed_seconds: z.number().int().min(0).max(3_600).nullable().optional(),
});

export async function POST(request: NextRequest, context: RouteContext<"/api/coaching-sessions/[sessionId]/answers">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能提交训练回答" }, { status: 401 });
  const { sessionId } = await context.params;
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "训练回答格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/coaching-sessions/${encodeURIComponent(sessionId)}/answers`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("专项训练回答提交失败", { cause: error });
    return NextResponse.json({ detail: "训练评价生成超时或服务暂时不可用" }, { status: 502 });
  }
}
