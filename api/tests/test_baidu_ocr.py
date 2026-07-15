import json

import httpx
import pytest

from interview_copilot.providers.baidu_ocr import (
    MAX_OCR_PDF_BYTES,
    BaiduOCR,
    BaiduOCRConfig,
    BaiduOCRError,
)


@pytest.mark.asyncio
async def test_recognizes_pdf_pages_and_reuses_oauth_token() -> None:
    token_requests = 0
    page_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests, page_requests
        if request.url.path.endswith("/oauth/2.0/token"):
            token_requests += 1
            return httpx.Response(
                200,
                json={"access_token": "temporary-token", "expires_in": 3600},
            )
        page_requests += 1
        body = request.content.decode("utf-8")
        assert "access_token=temporary-token" in str(request.url)
        page = "1" if "pdf_file_num=1" in body else "2"
        return httpx.Response(
            200,
            json={"words_result": [{"words": f"第{page}页内容"}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = BaiduOCR(
        BaiduOCRConfig(api_key="api-key", secret_key="secret-key"),
        client=client,
    )
    try:
        text = await provider.recognize_pdf(b"%PDF-test", page_count=2)
        repeated = await provider.recognize_pdf(b"%PDF-test", page_count=1)
    finally:
        await client.aclose()

    assert text == "第1页内容\n\n第2页内容"
    assert repeated == "第1页内容"
    assert token_requests == 1
    assert page_requests == 3


@pytest.mark.asyncio
async def test_rejects_vendor_error_without_leaking_response_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(
                {"error_code": 17, "error_msg": "Open api daily request limit reached"}
            ).encode(),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = BaiduOCR(
        BaiduOCRConfig(api_key="", secret_key="", access_token="token"),
        client=client,
    )
    try:
        with pytest.raises(BaiduOCRError, match="daily request limit") as caught:
            await provider.recognize_pdf(b"%PDF-test", page_count=1)
    finally:
        await client.aclose()

    assert "token" not in str(caught.value)
    assert "%PDF" not in str(caught.value)


@pytest.mark.asyncio
async def test_rejects_oversized_scanned_pdf_before_network() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    provider = BaiduOCR(
        BaiduOCRConfig(api_key="", secret_key="", access_token="token"),
        client=client,
    )
    try:
        with pytest.raises(ValueError, match="10MB"):
            await provider.recognize_pdf(
                b"%PDF-" + b"0" * MAX_OCR_PDF_BYTES,
                page_count=1,
            )
    finally:
        await client.aclose()
