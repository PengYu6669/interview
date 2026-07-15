from dataclasses import dataclass
from typing import Protocol

from interview_copilot.document_parser import ParsedDocument, parse_document

from .retrieval.normalization import normalize_document_text


class PDFOCR(Protocol):
    async def recognize_pdf(self, content: bytes, *, page_count: int) -> str: ...


@dataclass(frozen=True, slots=True)
class ProcessedDocument:
    document: ParsedDocument
    warnings: list[str]


async def process_document(
    *,
    filename: str,
    content: bytes,
    ocr: PDFOCR | None,
) -> ProcessedDocument:
    parsed = parse_document(filename, content)
    if parsed.text or parsed.media_type != "application/pdf":
        normalized = normalize_document_text(parsed.text, pages=parsed.pages)
        parsed.text = normalized.text
        parsed.pages = None
        return ProcessedDocument(document=parsed, warnings=list(normalized.warnings))
    if ocr is None:
        return ProcessedDocument(
            document=parsed,
            warnings=["没有找到可选择的文本，且尚未配置百度 OCR"],
        )
    text = await ocr.recognize_pdf(content, page_count=parsed.page_count or 0)
    normalized = normalize_document_text(text)
    return ProcessedDocument(
        document=ParsedDocument(
            filename=parsed.filename,
            media_type=parsed.media_type,
            text=normalized.text,
            page_count=parsed.page_count,
        ),
        warnings=[
            "扫描版 PDF 已通过百度 OCR 识别，请重点校对错别字和段落顺序",
            *normalized.warnings,
        ],
    )
