import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const createSchema = z.object({
  mode: z.enum(["structured_expression", "business_sense"]),
  channel: z.enum(["text", "voice"]),
  target_role: z.string().min(1).max(150),
  training_goal: z.string().max(500),
  source_ids: z.array(z.string().uuid()).max(30),
});

export async function GET(request: NextRequest) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以查看专项训练" }, { status: 401 });
  const rawLimit = Number(request.nextUrl.searchParams.get("limit") ?? "5");
  const limit = Number.isInteger(rawLimit) && rawLimit >= 1 && rawLimit <= 20 ? rawLimit : 5;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/coaching-sessions?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("专项训练记录读取失败", { cause: error });
    return NextResponse.json({ detail: "专项训练记录暂时无法读取" }, { status: 502 });
  }
}

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能创建专项训练" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "专项训练设置不完整" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/coaching-sessions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("专项训练创建失败", { cause: error });
    return NextResponse.json({ detail: "训练任务生成超时或服务暂时不可用" }, { status: 502 });
  }
}
