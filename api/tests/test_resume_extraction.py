import pytest

from interview_copilot.application.resume_extraction import (
    ExtractResumeProfile,
    normalize_document_text,
)
from interview_copilot.domain.resume import EvidenceItem, ResumeProfile


class StubResumeExtractor:
    async def extract(self, *, resume_text: str, jd: str, target_role: str) -> ResumeProfile:
        return ResumeProfile(
            target_role=target_role,
            summary="候选人使用 FastAPI 开发服务",
            skills=[EvidenceItem(value="FastAPI", evidence="使用 FastAPI 开发服务")],
        )


def test_normalizes_only_whitespace_and_line_endings() -> None:
    assert normalize_document_text("第一行\r\n第二行  \n\n\n\n末行") == (
        "第一行\n第二行\n\n\n末行"
    )


@pytest.mark.asyncio
async def test_extracts_a_versioned_profile() -> None:
    use_case = ExtractResumeProfile(StubResumeExtractor(), model_name="test-model")

    result = await use_case.execute(
        resume_text="使用 FastAPI 开发服务",
        jd="需要 Python 经验",
        target_role="后端工程师",
    )

    assert result.model == "test-model"
    assert result.prompt_version == "resume-extraction-v1"
    assert result.profile.schema_version == "1.0"
    assert result.profile.skills[0].evidence == "使用 FastAPI 开发服务"


@pytest.mark.asyncio
async def test_rejects_empty_normalized_resume() -> None:
    use_case = ExtractResumeProfile(StubResumeExtractor(), model_name="test-model")

    with pytest.raises(ValueError, match="简历文本不能为空"):
        await use_case.execute(resume_text=" \n ", jd="", target_role="后端工程师")
