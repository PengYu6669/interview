import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";
import { careerProfileRequestSchema } from "@/lib/career";

async function forward(request: NextRequest, method: "PUT" | "DELETE") {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能保存求职目标" }, { status: 401 });
  let body: string | undefined;
  if (method === "PUT") {
    let payload: unknown;
    try { payload = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
    const parsed = careerProfileRequestSchema.safeParse(payload);
    if (!parsed.success) return NextResponse.json({ detail: "求职目标内容不完整" }, { status: 422 });
    body = JSON.stringify(parsed.data);
  }
  try {
    const response = await fetch(`${API_BASE_URL}/v1/career/profile`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(method === "PUT" ? { "Content-Type": "application/json" } : {}) },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("求职目标保存失败", { cause: error });
    return NextResponse.json({ detail: "求职目标暂时无法保存" }, { status: 502 });
  }
}

export async function PUT(request: NextRequest) { return forward(request, "PUT"); }
export async function DELETE(request: NextRequest) { return forward(request, "DELETE"); }
