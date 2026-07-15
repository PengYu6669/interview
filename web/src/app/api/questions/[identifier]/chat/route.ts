import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function GET(_request: NextRequest, context: { params: Promise<{ identifier: string }> }) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以查看题库对话" }, { status: 401 });
  const { identifier } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/${encodeURIComponent(identifier)}/chat`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库对话读取失败", { cause: error });
    return NextResponse.json({ detail: "题库对话暂时无法读取" }, { status: 502 });
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ identifier: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以使用带引用问答" }, { status: 401 });
  const { identifier } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/${encodeURIComponent(identifier)}/chat`, {
      method: "POST",
      body: JSON.stringify(await request.json()),
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库问答失败", { cause: error });
    return NextResponse.json({ detail: "问答超时或 AI 服务暂时不可用" }, { status: 502 });
  }
}
