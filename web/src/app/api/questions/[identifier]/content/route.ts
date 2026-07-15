import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function PUT(request: NextRequest, context: { params: Promise<{ identifier: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以编辑个人题目" }, { status: 401 });
  const { identifier } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/${encodeURIComponent(identifier)}/content`, {
      method: "PUT",
      body: JSON.stringify(await request.json()),
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      signal: AbortSignal.timeout(120_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题目内容保存失败", { cause: error });
    return NextResponse.json({ detail: "保存超时或题库服务暂时不可用" }, { status: 502 });
  }
}
