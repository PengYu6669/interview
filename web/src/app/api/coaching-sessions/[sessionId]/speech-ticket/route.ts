import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function POST(request: NextRequest, context: RouteContext<"/api/coaching-sessions/[sessionId]/speech-ticket">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能使用语音训练" }, { status: 401 });
  const { sessionId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/coaching-sessions/${encodeURIComponent(sessionId)}/speech-ticket`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("专项训练语音票据获取失败", { cause: error });
    return NextResponse.json({ detail: "语音服务暂时无法启动" }, { status: 502 });
  }
}
