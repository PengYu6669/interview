import { NextResponse } from "next/server";

const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = new Set(["pdf", "docx", "md", "txt"]);
const API_BASE_URL = process.env.INTERVIEW_API_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const incoming = await request.formData();
  const file = incoming.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "请选择一个简历文件" }, { status: 400 });
  }
  if (file.size === 0) {
    return NextResponse.json({ detail: "文件内容为空" }, { status: 422 });
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    return NextResponse.json({ detail: "文件不能超过 20MB" }, { status: 413 });
  }
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    return NextResponse.json({ detail: "仅支持 PDF、DOCX、Markdown 和 TXT" }, { status: 415 });
  }

  const outgoing = new FormData();
  outgoing.set("file", file, file.name);

  try {
    const response = await fetch(`${API_BASE_URL}/v1/documents/parse`, {
      method: "POST",
      body: outgoing,
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    const payload: unknown = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("文档解析服务请求失败", { cause: error });
    return NextResponse.json(
      { detail: "文档解析服务暂时不可用，请稍后重试" },
      { status: 502 },
    );
  }
}
