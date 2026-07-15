import re
from typing import Protocol

from interview_copilot.domain.resume import ResumeExtractionResult, ResumeProfile

PROMPT_VERSION = "resume-extraction-v1"
MAX_RESUME_CHARACTERS = 80_000
MAX_JD_CHARACTERS = 30_000


class ResumeExtractionError(RuntimeError):
    pass


class ResumeExtractor(Protocol):
    async def extract(self, *, resume_text: str, jd: str, target_role: str) -> ResumeProfile: ...


def normalize_document_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{4,}", "\n\n\n", normalized)
    return normalized.strip()


class ExtractResumeProfile:
    def __init__(self, extractor: ResumeExtractor, *, model_name: str) -> None:
        self._extractor = extractor
        self._model_name = model_name

    async def execute(
        self, *, resume_text: str, jd: str, target_role: str
    ) -> ResumeExtractionResult:
        normalized_resume = normalize_document_text(resume_text)
        normalized_jd = normalize_document_text(jd)
        normalized_role = target_role.strip()

        if not normalized_resume:
            raise ValueError("简历文本不能为空")
        if len(normalized_resume) > MAX_RESUME_CHARACTERS:
            raise ValueError("简历文本超过结构化提取长度限制")
        if len(normalized_jd) > MAX_JD_CHARACTERS:
            raise ValueError("岗位描述超过结构化提取长度限制")
        if not normalized_role:
            raise ValueError("目标岗位不能为空")

        profile = await self._extractor.extract(
            resume_text=normalized_resume,
            jd=normalized_jd,
            target_role=normalized_role,
        )
        return ResumeExtractionResult(
            profile=profile,
            model=self._model_name,
            prompt_version=PROMPT_VERSION,
        )
