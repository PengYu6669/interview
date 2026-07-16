import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

const idSchema = z.string().uuid();

export async function GET(_: NextRequest, context: { params: Promise<{ jobId: string }> }) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能查看后台任务" }, { status: 401 });
  const parsed = idSchema.safeParse((await context.params).jobId);
  if (!parsed.success) return NextResponse.json({ detail: "任务编号不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/jobs/${parsed.data}`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("后台任务状态读取失败", { cause: error });
    return NextResponse.json({ detail: "后台任务状态暂时无法读取" }, { status: 502 });
  }
}
