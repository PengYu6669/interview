import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { weeklyPlanRequestSchema } from "@/lib/career";

export async function PUT(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能保存周计划" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = weeklyPlanRequestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "周计划内容不完整" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/weekly-plan`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("周计划保存失败", { cause: error });
    return NextResponse.json({ detail: "周计划暂时无法保存" }, { status: 502 });
  }
}
