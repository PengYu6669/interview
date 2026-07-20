import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET(request: NextRequest) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能管理用户" }, { status: 401 });
  const query = request.nextUrl.searchParams.get("query")?.trim() ?? "";
  try {
    const response = await fetch(`${API_BASE_URL}/v1/admin/users?query=${encodeURIComponent(query)}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("管理员用户列表读取失败", { cause: error });
    return NextResponse.json({ detail: "用户列表暂时无法读取" }, { status: 502 });
  }
}
