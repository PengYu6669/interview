import { NextResponse } from "next/server";
import { API_BASE_URL, readJsonResponse, sessionToken } from "@/lib/auth-server";

export async function GET(_request: Request, context: { params: Promise<{ identifier: string }> }) {
  const { identifier } = await context.params;
  try {
    const token = await sessionToken();
    const response = await fetch(`${API_BASE_URL}/v1/questions/${encodeURIComponent(identifier)}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: AbortSignal.timeout(10_000),
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题目详情读取失败", { cause: error });
    return NextResponse.json({ detail: "题库服务暂时不可用" }, { status: 502 });
  }
}
