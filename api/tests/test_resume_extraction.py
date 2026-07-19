import json
from uuid import UUID, uuid4

import httpx
import pytest

from interview_copilot.application.resume_extraction import (
    ExtractResumeProfile,
    ResumeExtractionError,
    normalize_document_text,
)
from interview_copilot.domain.resume import EvidenceItem, ResumeExtractionResult, ResumeProfile
from interview_copilot.providers.deepseek import DeepSeekResumeExtractor


class StubResumeExtractor:
    def __init__(self) -> None:
        self.calls = 0

    async def extract(self, *, resume_text: str, jd: str, target_role: str) -> ResumeProfile:
        self.calls += 1
        return ResumeProfile(
            target_role=target_role,
            summary="候选人使用 FastAPI 开发服务",
            skills=[EvidenceItem(value="FastAPI", evidence="使用 FastAPI 开发服务")],
        )


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[tuple[UUID, str], ResumeExtractionResult] = {}

    def get(self, *, user_id: UUID, fingerprint: str) -> ResumeExtractionResult | None:
        return self.values.get((user_id, fingerprint))

    def put(
        self,
        *,
        user_id: UUID,
        fingerprint: str,
        result: ResumeExtractionResult,
    ) -> None:
        self.values[(user_id, fingerprint)] = result


def test_normalizes_only_whitespace_and_line_endings() -> None:
    assert normalize_document_text("第一行\r\n第二行  \n\n\n\n末行") == ("第一行\n第二行\n\n\n末行")


@pytest.mark.asyncio
async def test_extracts_a_versioned_profile() -> None:
    use_case = ExtractResumeProfile(StubResumeExtractor(), model_name="test-model")

    result = await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
    )

    assert result.model == "test-model"
    assert result.prompt_version == "resume-extraction-v2-compact"
    assert result.profile.schema_version == "1.1"
    assert result.profile.skills[0].evidence == "使用 FastAPI 开发服务"


@pytest.mark.asyncio
async def test_rejects_empty_normalized_resume() -> None:
    use_case = ExtractResumeProfile(StubResumeExtractor(), model_name="test-model")

    with pytest.raises(ValueError, match="简历文本不能为空"):
        await use_case.execute(resume_text=" \n ", jd="", target_role="后端工程师")


@pytest.mark.asyncio
async def test_reuses_extraction_only_for_same_user_and_context() -> None:
    extractor = StubResumeExtractor()
    use_case = ExtractResumeProfile(extractor, model_name="test-model", cache=MemoryCache())
    owner = uuid4()

    first = await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
        user_id=owner,
    )
    cached = await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
        user_id=owner,
    )
    await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
        user_id=uuid4(),
    )

    assert cached == first
    assert extractor.calls == 2


@pytest.mark.asyncio
async def test_extracts_again_when_resume_changes() -> None:
    extractor = StubResumeExtractor()
    use_case = ExtractResumeProfile(extractor, model_name="test-model", cache=MemoryCache())
    owner = uuid4()

    await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
        user_id=owner,
    )
    await use_case.execute(
        resume_text="使用 FastAPI 开发服务，并负责 PostgreSQL 优化",
        jd="需要 Python 经验",
        target_role="后端工程师",
        user_id=owner,
    )

    assert extractor.calls == 2


def _deepseek_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


@pytest.mark.asyncio
async def test_deepseek_repairs_invalid_structured_output_once() -> None:
    requests: list[dict[str, object]] = []
    valid = ResumeProfile(
        target_role="后端工程师",
        summary="候选人使用 FastAPI 开发服务",
    ).model_dump_json()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            return _deepseek_response('{"target_role": 42}')
        return _deepseek_response(valid)

    client = httpx.AsyncClient(
        base_url="https://example.invalid",
        transport=httpx.MockTransport(handler),
    )
    provider = DeepSeekResumeExtractor(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        client=client,
    )
    try:
        result = await provider.extract(
            resume_text="使用 FastAPI 开发服务",
            jd="需要 Python 经验",
            target_role="后端工程师",
        )
    finally:
        await client.aclose()

    assert result.target_role == "后端工程师"
    assert len(requests) == 2
    repair_messages = requests[1]["messages"]
    assert isinstance(repair_messages, list)
    assert "校验错误路径：target_role" in repair_messages[-1]["content"]


@pytest.mark.asyncio
async def test_deepseek_reports_failure_after_repair_is_still_invalid() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return _deepseek_response('{"target_role": 42}')

    client = httpx.AsyncClient(
        base_url="https://example.invalid",
        transport=httpx.MockTransport(handler),
    )
    provider = DeepSeekResumeExtractor(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        client=client,
    )
    try:
        with pytest.raises(ResumeExtractionError, match="自动修复后仍未通过校验"):
            await provider.extract(
                resume_text="使用 FastAPI 开发服务",
                jd="需要 Python 经验",
                target_role="后端工程师",
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_truncated_output_does_not_trigger_a_second_paid_call() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _deepseek_response('{"target_role":"后端工程师')

    client = httpx.AsyncClient(
        base_url="https://example.invalid",
        transport=httpx.MockTransport(handler),
    )
    provider = DeepSeekResumeExtractor(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        client=client,
    )
    try:
        with pytest.raises(ResumeExtractionError, match="超过输出限制"):
            await provider.extract(
                resume_text="使用 FastAPI 开发服务",
                jd="需要 Python 经验",
                target_role="后端工程师",
            )
    finally:
        await client.aclose()

    assert calls == 1
