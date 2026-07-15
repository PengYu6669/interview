import { NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录状态已失效" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/interview-sessions/history`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("训练记录读取失败", { cause: error });
    return NextResponse.json({ detail: "训练记录暂时无法读取" }, { status: 502 });
  }
}
