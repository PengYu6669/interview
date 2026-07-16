import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { weeklyPlanItemStatusRequestSchema } from "@/lib/career";

export async function PATCH(request: NextRequest, context: RouteContext<"/api/career/weekly-plan/[planId]/items/[itemId]">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能更新计划事项" }, { status: 401 });
  const { planId, itemId } = await context.params;
  if (!z.string().uuid().safeParse(planId).success || !z.string().uuid().safeParse(itemId).success) {
    return NextResponse.json({ detail: "计划事项编号格式不正确" }, { status: 422 });
  }
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = weeklyPlanItemStatusRequestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "计划事项状态不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/weekly-plan/${encodeURIComponent(planId)}/items/${encodeURIComponent(itemId)}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("计划事项更新失败", { cause: error });
    return NextResponse.json({ detail: "计划事项暂时无法更新" }, { status: 502 });
  }
}
