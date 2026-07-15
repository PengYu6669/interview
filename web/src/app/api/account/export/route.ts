import { NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "请先登录" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/account/export`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      return NextResponse.json(await readJsonResponse(response), { status: response.status });
    }
    const payload = await response.text();
    const date = new Date().toISOString().slice(0, 10);
    return new Response(payload, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": `attachment; filename="interview-copilot-${date}.json"`,
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    console.error("账号数据导出失败", { cause: error });
    return NextResponse.json({ detail: "账号数据暂时无法导出" }, { status: 502 });
  }
}
