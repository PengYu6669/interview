import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

const schema = z.object({ text: z.string().trim().min(1).max(5_000) });

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后才能播放面试官语音" }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ detail: "请求体必须是有效 JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ detail: "合成文本格式不正确" }, { status: 422 });
  try {
    const response = await fetch(`${API_BASE_URL}/v1/tts/xfyun`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: AbortSignal.timeout(45_000),
    });
    if (!response.ok) return NextResponse.json(await readJsonResponse(response), { status: response.status });
    return new NextResponse(await response.arrayBuffer(), { status: 200, headers: { "Content-Type": response.headers.get("Content-Type") ?? "audio/mpeg", "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("面试官语音合成失败", { cause: error });
    return NextResponse.json({ detail: "语音合成超时或服务暂时不可用" }, { status: 502 });
  }
}
