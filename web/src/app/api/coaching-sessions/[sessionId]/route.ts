import { NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET(_request: Request, context: RouteContext<"/api/coaching-sessions/[sessionId]">) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以继续专项训练" }, { status: 401 });
  const { sessionId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/coaching-sessions/${encodeURIComponent(sessionId)}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("专项训练读取失败", { cause: error });
    return NextResponse.json({ detail: "专项训练暂时无法读取" }, { status: 502 });
  }
}
