import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { INTERVIEW_TYPE_VALUES } from "@/lib/training-context";

const schema = z.object({ resume_filename: z.string().max(255), resume_text: z.string().min(1).max(80_000), jd: z.string().max(30_000), target_role: z.string().min(1).max(150), target_company: z.string().max(100).default(""), target_level: z.enum(["intern", "campus", "mid", "senior"]).default("campus"), interview_round: z.enum(["first", "second", "final", "manager"]).default("first"), interview_type: z.enum(INTERVIEW_TYPE_VALUES).default("comprehensive"), mode: z.enum(["relaxed", "normal", "stress"]), duration_minutes: z.number().int().min(1).max(180), pressure_level: z.number().int().min(1).max(5), depth_level: z.number().int().min(1).max(5), guidance_level: z.number().int().min(1).max(5), question_ids: z.array(z.string().uuid()).max(20).default([]), training_focus: z.string().max(500).default("") });

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "尚未登录，继续使用本次会话即可" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "训练草稿内容格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/drafts`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(parsed.data), cache: "no-store", signal: AbortSignal.timeout(15_000) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("训练草稿保存失败", { cause: error });
    return NextResponse.json({ detail: "训练草稿暂时无法保存" }, { status: 502 });
  }
}
