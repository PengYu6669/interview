import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function POST(request: NextRequest, context: RouteContext<"/api/questions/documents/[documentId]/regenerate">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能重新生成题库" }, { status: 401 });
  const { documentId } = await context.params;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/documents/${encodeURIComponent(documentId)}/regenerate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库资料重新生成失败", { cause: error });
    return NextResponse.json({ detail: "重新生成超时或服务暂时不可用" }, { status: 502 });
  }
}
