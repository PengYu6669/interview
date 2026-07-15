import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function DELETE(request: NextRequest, context: RouteContext<"/api/career/weekly-plan/[planId]">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能删除周计划" }, { status: 401 });
  const { planId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/weekly-plan/${encodeURIComponent(planId)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("周计划删除失败", { cause: error });
    return NextResponse.json({ detail: "周计划暂时无法删除" }, { status: 502 });
  }
}
