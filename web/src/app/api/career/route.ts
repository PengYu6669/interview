import { NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以查看求职计划" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("求职计划读取失败", { cause: error });
    return NextResponse.json({ detail: "求职计划暂时无法读取" }, { status: 502 });
  }
}
