import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth";
import { accountDataSummarySchema, deleteAccountRequestSchema } from "@/lib/account";
import {
  API_BASE_URL,
  readJsonResponse,
  rejectCrossOrigin,
  sessionToken,
} from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "请先登录" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/account`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) return NextResponse.json(payload, { status: response.status });
    const parsed = accountDataSummarySchema.safeParse(payload);
    if (!parsed.success) {
      return NextResponse.json({ detail: "账号服务返回了无效数据" }, { status: 502 });
    }
    return NextResponse.json(parsed.data);
  } catch (error) {
    console.error("账号数据概览读取失败", { cause: error });
    return NextResponse.json({ detail: "账号数据暂时无法读取" }, { status: 502 });
  }
}

export async function DELETE(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "请先登录" }, { status: 401 });
  const parsed = deleteAccountRequestSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json(
      { detail: parsed.error.issues[0]?.message ?? "注销请求无效" },
      { status: 422 },
    );
  }
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/account`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) {
      return NextResponse.json(await readJsonResponse(response), { status: response.status });
    }
    const result = NextResponse.json({ success: true });
    result.cookies.set(AUTH_COOKIE_NAME, "", {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 0,
    });
    return result;
  } catch (error) {
    console.error("账号注销失败", { cause: error });
    return NextResponse.json({ detail: "账号暂时无法注销，请稍后重试" }, { status: 502 });
  }
}
