import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const idSchema = z.string().uuid();
const updateSchema = z.object({
  title: z.string().trim().min(1).max(250),
  prompt: z.string().trim().min(1).max(8_000),
  difficulty: z.enum(["基础", "进阶", "高级"]),
  question_type: z.string().trim().min(1).max(30),
  framework: z.string().trim().min(1).max(30),
  intent: z.string().trim().min(1).max(4_000),
  answer_outline: z.array(z.string().trim().min(1).max(500)).min(1).max(12),
  common_mistakes: z.array(z.string().trim().min(1).max(500)).min(1).max(12),
  topic_names: z.array(z.string().trim().min(1).max(100)).min(1).max(12),
  content_markdown: z.string().max(80_000),
}).strict();

async function contextData(context: RouteContext<"/api/admin/questions/[questionId]">) {
  const { questionId } = await context.params;
  return idSchema.safeParse(questionId);
}

export async function GET(
  _request: NextRequest,
  context: RouteContext<"/api/admin/questions/[questionId]">,
) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能管理题库" }, { status: 401 });
  const parsedId = await contextData(context);
  if (!parsedId.success) return NextResponse.json({ detail: "题目编号格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/admin/questions/${encodeURIComponent(parsedId.data)}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("管理题目读取失败", { cause: error });
    return NextResponse.json({ detail: "题目暂时无法读取" }, { status: 502 });
  }
}

export async function PUT(
  request: NextRequest,
  context: RouteContext<"/api/admin/questions/[questionId]">,
) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能管理题库" }, { status: 401 });
  const parsedId = await contextData(context);
  if (!parsedId.success) return NextResponse.json({ detail: "题目编号格式不正确" }, { status: 422 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = updateSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "请检查题目必填内容和长度" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/admin/questions/${encodeURIComponent(parsedId.data)}`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("管理题目保存失败", { cause: error });
    return NextResponse.json({ detail: "题目暂时无法保存" }, { status: 502 });
  }
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/admin/questions/[questionId]">,
) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能管理题库" }, { status: 401 });
  const parsedId = await contextData(context);
  if (!parsedId.success) return NextResponse.json({ detail: "题目编号格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/admin/questions/${encodeURIComponent(parsedId.data)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("管理员删除题目失败", { cause: error });
    return NextResponse.json({ detail: "题目暂时无法删除" }, { status: 502 });
  }
}
