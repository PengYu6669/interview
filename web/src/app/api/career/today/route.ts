import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET(request: NextRequest) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以查看今日计划" }, { status: 401 });
  const requestedDate = request.nextUrl.searchParams.get("date");
  const parsedDate = z.iso.date().safeParse(requestedDate);
  if (!parsedDate.success) return NextResponse.json({ detail: "今日计划日期格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/today?date=${encodeURIComponent(parsedDate.data)}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("今日计划读取失败", { cause: error });
    return NextResponse.json({ detail: "今日计划暂时无法读取" }, { status: 502 });
  }
}
