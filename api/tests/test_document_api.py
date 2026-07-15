from io import BytesIO

from fastapi.testclient import TestClient

from interview_copilot.main import app

client = TestClient(app)


def test_parse_endpoint_returns_a_typed_result() -> None:
    response = client.post(
        "/v1/documents/parse",
        files={"file": ("resume.md", BytesIO("项目经历".encode()), "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "resume.md",
        "media_type": "text/markdown",
        "text": "项目经历",
        "page_count": None,
        "warnings": ["文档可用文字较少，请确认文件内容是否完整"],
    }


def test_parse_endpoint_rejects_spoofed_pdf() -> None:
    response = client.post(
        "/v1/documents/parse",
        files={"file": ("resume.pdf", BytesIO(b"not a pdf"), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "文件内容不是有效的 PDF"
