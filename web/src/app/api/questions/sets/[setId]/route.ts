import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET(_: NextRequest, context: RouteContext<"/api/questions/sets/[setId]">) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后查看题目集" }, { status: 401 });
  const { setId } = await context.params;
  if (!z.string().uuid().safeParse(setId).success) return NextResponse.json({ detail: "题目集编号格式不正确" }, { status: 422 });
  const response = await fetch(`${API_BASE_URL}/v1/questions/sets/${encodeURIComponent(setId)}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await readJsonResponse(response), { status: response.status });
}
