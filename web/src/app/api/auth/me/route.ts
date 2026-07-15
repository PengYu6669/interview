import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE_NAME, authUserSchema } from "@/lib/auth";
import { API_BASE_URL, readJsonResponse } from "@/lib/auth-server";

export async function GET() {
  const token = (await cookies()).get(AUTH_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "尚未登录" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10_000) });
    const payload = await readJsonResponse(response);
    if (!response.ok) return NextResponse.json(payload, { status: response.status });
    const parsed = authUserSchema.safeParse(payload);
    if (!parsed.success) return NextResponse.json({ detail: "账号服务返回了无效用户信息" }, { status: 502 });
    return NextResponse.json({ user: parsed.data });
  } catch (error) {
    console.error("当前用户查询失败", { cause: error });
    return NextResponse.json({ detail: "账号服务暂时不可用" }, { status: 502 });
  }
}
