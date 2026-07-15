import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { boardSnapshotSchema, boardStateSchema } from "@/lib/interview-board";

const requestSchema = z.object({
  client_snapshot_id: z.string().uuid(),
  base_revision: z.number().int().nonnegative(),
  state: boardStateSchema,
});

async function forward(sessionId: string, token: string, init?: RequestInit) {
  return fetch(`${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/board`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
}

export async function GET(_request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能读取系统设计白板" }, { status: 401 });
  const { sessionId } = await context.params;
  try {
    const response = await forward(sessionId, token);
    const payload = await readJsonResponse(response);
    if (response.ok && payload !== null) {
      const parsed = boardSnapshotSchema.safeParse(payload);
      if (!parsed.success) return NextResponse.json({ detail: "白板服务返回了无效数据" }, { status: 502 });
      return NextResponse.json(parsed.data, { status: response.status });
    }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("系统设计白板读取失败", { cause: error });
    return NextResponse.json({ detail: "系统设计白板暂时无法读取" }, { status: 502 });
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ sessionId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能保存系统设计白板" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = requestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "白板数据格式不正确" }, { status: 422 });
  const { sessionId } = await context.params;
  try {
    const response = await forward(sessionId, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parsed.data) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("系统设计白板保存失败", { cause: error });
    return NextResponse.json({ detail: "系统设计白板暂时无法保存" }, { status: 502 });
  }
}

