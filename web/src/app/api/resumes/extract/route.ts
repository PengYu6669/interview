import { NextResponse } from "next/server";
import { z } from "zod";

const API_BASE_URL = process.env.INTERVIEW_API_URL ?? "http://localhost:8000";

const requestSchema = z.object({
  resume_text: z.string().trim().min(1).max(80_000),
  jd: z.string().max(30_000),
  target_role: z.string().trim().min(1).max(150),
});

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 });
  }
  const parsed = requestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ detail: "简历、JD 或目标岗位格式不正确" }, { status: 422 });
  }

  try {
    const response = await fetch(`${API_BASE_URL}/v1/resumes/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(90_000),
    });
    const payload: unknown = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("简历结构化提取服务请求失败", { cause: error });
    return NextResponse.json({ detail: "简历提取服务暂时不可用，请稍后重试" }, { status: 502 });
  }
}
