import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL, readJsonResponse } from "@/lib/auth-server";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.toString();
  try {
    const response = await fetch(`${API_BASE_URL}/v1/questions${query ? `?${query}` : ""}`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch (error) {
    console.error("题库列表读取失败", { cause: error });
    return NextResponse.json({ detail: "题库服务暂时不可用" }, { status: 502 });
  }
}
