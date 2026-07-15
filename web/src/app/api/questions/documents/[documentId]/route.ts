import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function DELETE(request: NextRequest, context: RouteContext<"/api/questions/documents/[documentId]">) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能删除题库资料" }, { status: 401 });
  const { documentId } = await context.params;
  if (!z.string().uuid().safeParse(documentId).success) return NextResponse.json({ detail: "题库资料编号格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库资料删除失败", { cause: error });
    return NextResponse.json({ detail: "题库资料暂时无法删除" }, { status: 502 });
  }
}
