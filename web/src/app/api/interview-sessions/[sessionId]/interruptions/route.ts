import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const schema = z.object({
  client_message_id: z.string().uuid(),
  partial_answer: z.string().trim().min(60).max(20_000),
  elapsed_seconds: z.number().int().min(12).max(55),
});

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录状态已失效" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "实时回答片段格式不正确" }, { status: 422 });
  const { sessionId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/interruptions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const payload = await readJsonResponse(response);
    if (response.status === 429 || response.status >= 500) {
      return NextResponse.json({ interrupted: false });
    }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("实时打断判断失败", { cause: error });
    return NextResponse.json({ interrupted: false });
  }
}
