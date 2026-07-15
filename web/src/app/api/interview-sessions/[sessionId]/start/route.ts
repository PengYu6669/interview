import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录状态已失效" }, { status: 401 });
  const { sessionId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/start`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("面试开始失败", { cause: error });
    return NextResponse.json({ detail: "面试会话暂时无法开始" }, { status: 502 });
  }
}
