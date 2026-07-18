import re
from dataclasses import dataclass

_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+")
_QUESTION_HEADING = re.compile(
    r"^(?:Q\s*\d{1,4}|问题\s*\d{1,4}|第\s*\d{1,4}\s*[题问])\s*[：:.、-]?\s*\S+",
    re.IGNORECASE,
)
_CHAPTER_HEADING = re.compile(
    r"^(?:[一二三四五六七八九十百]+[、.]|第[一二三四五六七八九十百\d]+[章节部分篇])\s*\S+"
)
_TAG_HEADING = re.compile(r"^[【\[][^】\]]{2,30}[】\]]\s*$")
_NUMBERED_HEADING = re.compile(r"^\d{1,3}(?:\.\d{1,3}){0,3}[、.]\s*\S+")
_PAGE_NUMBER = re.compile(r"^(?:[-—–]\s*)?第?\s*\d{1,4}\s*页?(?:\s*[-—–])?$")
_TOC_LEADER = re.compile(r"\.{4,}|…{3,}|·{5,}")


@dataclass(frozen=True, slots=True)
class RecoveredStructure:
    text: str
    high_confidence_headings: tuple[str, ...]
    removed_navigation_lines: int


def recover_document_structure(text: str) -> RecoveredStructure:
    """恢复常见文档层级；不改写正文，不确定的短行保持普通文本。"""

    output: list[str] = []
    headings: list[str] = []
    removed = 0
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            output.append("")
            continue
        if _PAGE_NUMBER.fullmatch(line) or (
            _TOC_LEADER.search(line) and re.search(r"\d{1,4}\s*$", line)
        ):
            removed += 1
            continue
        if _MARKDOWN_HEADING.match(line):
            output.append(line)
            continue
        if _QUESTION_HEADING.match(line):
            output.extend((f"## {line}", ""))
            headings.append(line)
            continue
        if _CHAPTER_HEADING.match(line):
            output.extend((f"# {line}", ""))
            continue
        if _TAG_HEADING.match(line):
            output.extend((f"### {line}", ""))
            continue
        if _NUMBERED_HEADING.match(line) and len(line) <= 80:
            output.extend((f"### {line}", ""))
            continue
        output.append(raw_line.strip())
    recovered = re.sub(r"\n{4,}", "\n\n\n", "\n".join(output)).strip()
    return RecoveredStructure(
        text=recovered,
        high_confidence_headings=tuple(dict.fromkeys(headings)),
        removed_navigation_lines=removed,
    )
