import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

async function proxy(sessionId: string, method: "GET" | "POST") {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录状态已失效" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/report`, {
      method,
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(method === "POST" ? 120_000 : 10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error(method === "POST" ? "面试报告生成失败" : "面试报告读取失败", { cause: error });
    return NextResponse.json({ detail: method === "POST" ? "面试报告生成超时" : "面试报告暂时无法读取" }, { status: 502 });
  }
}

export async function GET(_request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  return proxy((await context.params).sessionId, "GET");
}

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  return proxy((await context.params).sessionId, "POST");
}
