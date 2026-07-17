import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { INTERVIEW_TYPE_VALUES } from "@/lib/training-context";

const schema = z.object({ resume_filename: z.string().max(255).optional(), resume_text: z.string().min(1).max(80_000).optional(), jd: z.string().max(30_000).optional(), target_role: z.string().min(1).max(150).optional(), target_company: z.string().max(100).optional(), target_level: z.enum(["intern", "campus", "mid", "senior"]).optional(), interview_round: z.enum(["first", "second", "final", "manager"]).optional(), interview_type: z.enum(INTERVIEW_TYPE_VALUES).optional(), mode: z.string().max(30).optional(), duration_minutes: z.number().int().min(1).max(180).optional(), pressure_level: z.number().int().min(1).max(5).optional(), depth_level: z.number().int().min(1).max(5).optional(), guidance_level: z.number().int().min(1).max(5).optional(), question_ids: z.array(z.string().uuid()).max(20).optional(), training_focus: z.string().max(500).optional(), source_session_id: z.string().uuid().nullable().optional(), career_plan_item_id: z.string().uuid().nullable().optional(), extraction: z.record(z.string(), z.unknown()).nullable().optional() });

export async function GET(_request: NextRequest, context: { params: Promise<{ draftId: string }> }) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "尚未登录" }, { status: 401 });
  const { draftId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/drafts/${encodeURIComponent(draftId)}`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10_000) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("训练草稿读取失败", { cause: error });
    return NextResponse.json({ detail: "训练草稿暂时无法读取" }, { status: 502 });
  }
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ draftId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "尚未登录" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "训练草稿更新内容不正确" }, { status: 422 });
  const { draftId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/drafts/${encodeURIComponent(draftId)}`, { method: "PATCH", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(parsed.data), cache: "no-store", signal: AbortSignal.timeout(15_000) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("训练草稿更新失败", { cause: error });
    return NextResponse.json({ detail: "训练草稿暂时无法更新" }, { status: 502 });
  }
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ draftId: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "尚未登录" }, { status: 401 });
  const { draftId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/drafts/${encodeURIComponent(draftId)}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15_000) });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("训练草稿删除失败", { cause: error });
    return NextResponse.json({ detail: "训练草稿暂时无法删除" }, { status: 502 });
  }
}
