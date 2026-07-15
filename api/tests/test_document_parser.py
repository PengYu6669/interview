from io import BytesIO

import pymupdf
import pytest
from docx import Document

from interview_copilot.application.document_processing import process_document
from interview_copilot.document_parser import InvalidDocumentError, parse_document


def test_parses_utf8_text() -> None:
    parsed = parse_document("resume.md", "项目经历\nRAG 平台".encode())

    assert parsed.media_type == "text/markdown"
    assert "RAG 平台" in parsed.text


def test_parses_docx_content() -> None:
    stream = BytesIO()
    document = Document()
    document.add_paragraph("FastAPI 项目经历")
    document.save(stream)

    parsed = parse_document("resume.docx", stream.getvalue())

    assert parsed.media_type.endswith("document")
    assert parsed.text == "FastAPI 项目经历"


@pytest.mark.asyncio
async def test_native_pdf_removes_repeated_page_margins_in_production_flow() -> None:
    document = pymupdf.open()
    for index in range(1, 5):
        page = document.new_page()
        page.insert_text(
            (72, 72),
            f"Candidate Resume\nPage {index}\nProject {index}\nAPI design\nInternal Use",
        )
    content = document.tobytes()
    document.close()

    processed = await process_document(
        filename="resume.pdf",
        content=content,
        ocr=None,
    )

    assert "Candidate Resume" not in processed.document.text
    assert "Internal Use" not in processed.document.text
    assert "Project 3" in processed.document.text
    assert any("页眉或页脚" in warning for warning in processed.warnings)
    assert processed.document.pages is None


@pytest.mark.parametrize(
    ("filename", "content"),
    [("empty.md", b""), ("fake.pdf", b"not a pdf"), ("fake.docx", b"not a zip")],
)
def test_rejects_empty_or_spoofed_documents(filename: str, content: bytes) -> None:
    with pytest.raises(InvalidDocumentError):
        parse_document(filename, content)


def test_rejects_non_utf8_text() -> None:
    with pytest.raises(InvalidDocumentError, match="UTF-8"):
        parse_document("resume.txt", b"\xff\xfe")


@pytest.mark.asyncio
async def test_scanned_pdf_uses_configured_ocr() -> None:
    document = pymupdf.open()
    document.new_page()
    content = document.tobytes()
    document.close()

    class FakeOCR:
        async def recognize_pdf(self, value: bytes, *, page_count: int) -> str:
            assert value == content
            assert page_count == 1
            return "OCR 项目经历"

    processed = await process_document(
        filename="scan.pdf",
        content=content,
        ocr=FakeOCR(),
    )

    assert processed.document.text == "OCR 项目经历"
    assert "百度 OCR" in processed.warnings[0]
