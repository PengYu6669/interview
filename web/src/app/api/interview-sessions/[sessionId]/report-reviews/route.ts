import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { interviewReportReviewRequestSchema } from "@/lib/interview-report";

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/interview-sessions/[sessionId]/report-reviews">,
) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能提交报告异议" }, { status: 401 });
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 });
  }
  const parsed = interviewReportReviewRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ detail: "请填写至少 10 个字的异议理由" }, { status: 422 });
  }
  const { sessionId } = await context.params;
  try {
    const response = await fetch(
      `${API_BASE_URL}/v1/interview-sessions/${encodeURIComponent(sessionId)}/report-reviews`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
        cache: "no-store",
        signal: AbortSignal.timeout(parsed.data.action === "reevaluate" ? 90_000 : 10_000),
      },
    );
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("面试报告异议提交失败", { cause: error });
    return NextResponse.json(
      { detail: parsed.data.action === "reevaluate" ? "报告复核超时或服务暂时不可用" : "暂时无法更新能力画像" },
      { status: 502 },
    );
  }
}
