import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, authResponse, readJsonResponse, rejectCrossOrigin } from "@/lib/auth-server";

const schema = z.object({ username: z.string().trim().min(3).max(50), email: z.string().trim().email().max(320), password: z.string().min(6).max(128) });

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    const field = parsed.error.issues[0]?.path[0];
    const detail = field === "username" ? "用户名长度应为 3 至 50 位" : field === "email" ? "邮箱格式不正确" : "密码至少需要 6 位";
    return NextResponse.json({ detail }, { status: 422 });
  }
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parsed.data), cache: "no-store", signal: AbortSignal.timeout(15_000) });
    const payload = await readJsonResponse(response);
    if (!response.ok) return NextResponse.json(payload, { status: response.status });
    return authResponse(payload, 201);
  } catch (error) {
    console.error("注册服务请求失败", { cause: error });
    return NextResponse.json({ detail: "账号服务暂时不可用" }, { status: 502 });
  }
}
