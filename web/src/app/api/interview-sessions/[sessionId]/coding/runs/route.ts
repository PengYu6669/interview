import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { codingRunSchema } from "@/lib/interview-coding";

const runSchema = z.object({
  client_request_id: z.string().uuid(),
  snapshot_revision: z.number().int().nonnegative(),
});

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能运行代码" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = runSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "运行请求格式不正确" }, { status: 422 });
  const { sessionId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/coding/runs`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const payload = await readJsonResponse(response);
    if (response.ok) {
      const result = codingRunSchema.safeParse(payload);
      if (!result.success) return NextResponse.json({ detail: "Coding 服务返回了无效运行结果" }, { status: 502 });
      return NextResponse.json(result.data);
    }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("Coding 代码运行失败", { cause: error });
    return NextResponse.json({ detail: "代码运行服务暂时不可用" }, { status: 502 });
  }
}
