import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以导入题库" }, { status: 401 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions/import`, {
      method: "POST",
      body: await request.formData(),
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(180_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库文档导入失败", { cause: error });
    return NextResponse.json({ detail: "文档处理超时或服务暂时不可用" }, { status: 502 });
  }
}
