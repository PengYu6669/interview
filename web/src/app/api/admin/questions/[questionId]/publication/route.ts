import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const requestSchema = z.object({ published: z.boolean() }).strict();
const idSchema = z.string().uuid();

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/admin/questions/[questionId]/publication">,
) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能管理题库" }, { status: 401 });
  const { questionId } = await context.params;
  const parsedId = idSchema.safeParse(questionId);
  if (!parsedId.success) return NextResponse.json({ detail: "题目编号格式不正确" }, { status: 422 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = requestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "发布状态格式不正确" }, { status: 422 });
  try {
    const response = await fetch(
      `${API_BASE_URL}/v1/admin/questions/${encodeURIComponent(parsedId.data)}/publication`,
      {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
        cache: "no-store",
        signal: AbortSignal.timeout(10_000),
      },
    );
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题目发布状态更新失败", { cause: error });
    return NextResponse.json({ detail: "题目发布状态暂时无法更新" }, { status: 502 });
  }
}
