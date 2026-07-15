import { NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以查看个人题目" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/mine`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("个人题库读取失败", { cause: error });
    return NextResponse.json({ detail: "题库服务暂时不可用" }, { status: 502 });
  }
}
