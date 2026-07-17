import "server-only";

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME, authResultSchema, authUserSchema } from "./auth";
import type { AuthUser } from "./auth";

export const API_BASE_URL = process.env.INTERVIEW_API_URL ?? "http://localhost:8000";

export async function sessionToken(): Promise<string | null> {
  return (await cookies()).get(AUTH_COOKIE_NAME)?.value ?? null;
}

export async function currentUser(): Promise<AuthUser | null> {
  const token = await sessionToken();
  if (!token) return null;
  try {
    const response = await fetch(`${API_BASE_URL}/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) return null;
    const parsed = authUserSchema.safeParse(await readJsonResponse(response));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

export function safeInternalPath(requested: string | undefined, fallback = "/training"): string {
  if (!requested || !requested.startsWith("/") || requested.startsWith("//") || requested.includes("\\")) return fallback;
  try {
    const parsed = new URL(requested, "http://internal.local");
    if (parsed.origin !== "http://internal.local") return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

export function rejectCrossOrigin(request: NextRequest): NextResponse | null {
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "请求来源不受信任" }, { status: 403 });
  }
  return null;
}

export function authResponse(payload: unknown, status: number): NextResponse {
  const parsed = authResultSchema.safeParse(payload);
  if (!parsed.success) {
    return NextResponse.json({ detail: "账号服务返回了无效结果" }, { status: 502 });
  }
  const response = NextResponse.json({ user: parsed.data.user }, { status });
  const expires = new Date(parsed.data.expires_at);
  response.cookies.set(AUTH_COOKIE_NAME, parsed.data.session_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires,
  });
  return response;
}

export async function readJsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return { detail: "账号服务返回了无法解析的响应" };
  }
}
