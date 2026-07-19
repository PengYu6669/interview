import { z } from "zod";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  return typeof payload === "object" && payload && "detail" in payload
    ? String((payload as { detail: unknown }).detail)
    : fallback;
}

async function handleResponse(response: Response, fallback: string) {
  if (response.status === 204) return undefined;
  const payload: unknown = await response.json();
  if (!response.ok) throw new ApiError(errorMessage(payload, fallback), response.status);
  return payload;
}

export async function apiGet<T>(
  url: string,
  schema: z.ZodType<T>,
  opts?: { cache?: RequestCache; signal?: AbortSignal },
): Promise<T> {
  const response = await fetch(url, { cache: opts?.cache ?? "no-store", signal: opts?.signal });
  const payload = await handleResponse(response, "读取失败");
  if (payload === undefined) throw new ApiError("读取失败", 500);
  return schema.parse(payload);
}

export async function apiPost<T>(
  url: string,
  body: unknown,
  schema: z.ZodType<T>,
): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await handleResponse(response, "操作失败");
  return schema.parse(payload);
}

export async function apiPatch<T>(
  url: string,
  body: unknown,
  schema: z.ZodType<T>,
): Promise<T> {
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await handleResponse(response, "更新失败");
  return schema.parse(payload);
}

export async function apiDelete(url: string): Promise<void> {
  const response = await fetch(url, { method: "DELETE", cache: "no-store" });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => ({}));
    throw new ApiError(errorMessage(payload, "删除失败"), response.status);
  }
}

export async function apiUpload<T>(
  url: string,
  formData: FormData,
  schema: z.ZodType<T>,
): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  const payload = await handleResponse(response, "上传失败");
  return schema.parse(payload);
}

/**
 * Lightweight fetch + parse for endpoints that may return non-critical data.
 * Returns null on any failure instead of throwing.
 */
export async function apiGetOptional<T>(
  url: string,
  schema: z.ZodType<T>,
): Promise<T | null> {
  try {
    return await apiGet(url, schema);
  } catch {
    return null;
  }
}
