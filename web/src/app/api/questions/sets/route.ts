import { NextRequest, NextResponse } from "next/server";

import { API_BASE_URL, readJsonResponse, rejectCrossOrigin, sessionToken } from "@/lib/auth-server";

export async function GET() {
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后查看题目集" }, { status: 401 });
  const response = await fetch(`${API_BASE_URL}/v1/questions/sets`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await readJsonResponse(response), { status: response.status });
}

export async function POST(request: NextRequest) {
  const rejected = rejectCrossOrigin(request);
  if (rejected) return rejected;
  const token = await sessionToken();
  if (!token) return NextResponse.json({ detail: "登录后创建题目集" }, { status: 401 });
  const response = await fetch(`${API_BASE_URL}/v1/questions/sets`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(await request.json()),
  });
  return NextResponse.json(await readJsonResponse(response), { status: response.status });
}
