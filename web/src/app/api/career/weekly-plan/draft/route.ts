import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { weeklyPlanDraftRequestSchema } from "@/lib/career";

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能生成训练日程" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = weeklyPlanDraftRequestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "周一日期格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/weekly-plan/draft`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("AI 训练日程生成失败", { cause: error });
    return NextResponse.json({ detail: "AI 面试教练生成日程超时或暂时不可用" }, { status: 502 });
  }
}
