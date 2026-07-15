import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { codingWorkspaceSchema } from "@/lib/interview-coding";

const saveSchema = z.object({
  client_snapshot_id: z.string().uuid(),
  base_revision: z.number().int().nonnegative(),
  source: z.string().min(1).max(20_000),
  complexity_notes: z.string().max(2_000),
});

async function forward(sessionId: string, token: string, init?: RequestInit) {
  return fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/coding`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
}

export async function GET(_request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能读取 Coding Board" }, { status: 401 });
  const { sessionId } = await context.params;
  try {
    const response = await forward(sessionId, token);
    const payload = await readJsonResponse(response);
    if (response.ok) {
      const parsed = codingWorkspaceSchema.safeParse(payload);
      if (!parsed.success) return NextResponse.json({ detail: "Coding 服务返回了无效数据" }, { status: 502 });
      return NextResponse.json(parsed.data);
    }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("Coding 工作区读取失败", { cause: error });
    return NextResponse.json({ detail: "Coding 工作区暂时无法读取" }, { status: 502 });
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能保存代码" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = saveSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "代码快照格式不正确" }, { status: 422 });
  const { sessionId } = await context.params;
  try {
    const response = await forward(sessionId, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parsed.data) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("Coding 工作区保存失败", { cause: error });
    return NextResponse.json({ detail: "代码暂时无法保存" }, { status: 502 });
  }
}
