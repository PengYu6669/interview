import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

async function proxy(method: "GET" | "PUT", request: NextRequest, identifier: string) {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后可以保存学习状态和笔记" }, { status: 401 });
  const options: RequestInit = { method, headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10_000) };
  if (method === "PUT") { options.headers = { ...options.headers, "Content-Type": "application/json" }; options.body = JSON.stringify(await request.json()); }
  const response = await fetch(`${API_BASE_URL}/v1/questions/${encodeURIComponent(identifier)}/state`, options);
  return NextResponse.json(await readJsonResponse(response), { status: response.status });
}

export async function GET(request: NextRequest, context: { params: Promise<{ identifier: string }> }) {
  return proxy("GET", request, (await context.params).identifier);
}

export async function PUT(request: NextRequest, context: { params: Promise<{ identifier: string }> }) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  return proxy("PUT", request, (await context.params).identifier);
}
