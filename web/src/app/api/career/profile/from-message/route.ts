import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { careerProfileMessageRequestSchema } from "@/lib/career";

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能创建求职画像" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = careerProfileMessageRequestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "请用一句话说明你的求职目标" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/profile/from-message`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(75_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("对话式求职画像生成失败", { cause: error });
    return NextResponse.json({ detail: "求职画像暂时无法生成" }, { status: 502 });
  }
}
