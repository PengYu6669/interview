import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from .structure import recover_document_structure

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESSIVE_BLANK_LINES = re.compile(r"\n{4,}")
_SUSPICIOUS_GARBAGE = re.compile(r"(?:�|□|■|\?{4,})")


@dataclass(frozen=True, slots=True)
class NormalizedDocumentText:
    text: str
    warnings: tuple[str, ...]
    removed_repeated_lines: tuple[str, ...] = ()


def normalize_document_text(text: str, *, pages: list[str] | None = None) -> NormalizedDocumentText:
    """做可追溯的确定性清理，不用模型猜测或改写原意。"""

    normalized_pages = [_normalize_page(page) for page in pages] if pages else None
    removed: tuple[str, ...] = ()
    if normalized_pages and len(normalized_pages) >= 3:
        repeated = _repeated_margin_lines(normalized_pages)
        if repeated:
            removed = tuple(sorted(repeated))
            normalized_pages = [_remove_margin_lines(page, repeated) for page in normalized_pages]
        normalized = "\n\n".join(page for page in normalized_pages if page)
    else:
        normalized = _normalize_page(text)

    structure = recover_document_structure(normalized)
    normalized = structure.text
    warnings: list[str] = []
    if removed:
        warnings.append(f"已移除 {len(removed)} 条重复页眉或页脚，请确认正文未受影响")
    if structure.removed_navigation_lines:
        warnings.append(f"已忽略 {structure.removed_navigation_lines} 条目录点线或孤立页码")
    if structure.high_confidence_headings:
        warnings.append(f"已恢复 {len(structure.high_confidence_headings)} 个明确的问题或章节锚点")
    if _SUSPICIOUS_GARBAGE.search(normalized):
        warnings.append("文档中存在疑似乱码或 OCR 异常字符，请在继续前校对")
    if normalized and _useful_character_ratio(normalized) < 0.65:
        warnings.append("文档可识别文字比例偏低，检索和结构化结果可能不稳定")
    if len(normalized.strip()) < 80:
        warnings.append("文档可用文字较少，请确认文件内容是否完整")
    return NormalizedDocumentText(
        text=normalized.strip(), warnings=tuple(warnings), removed_repeated_lines=removed
    )


def _normalize_page(text: str) -> str:
    value = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    value = _CONTROL_CHARACTERS.sub("", value)
    lines = [re.sub(r"[ \t]+$", "", line).strip("\ufeff") for line in value.split("\n")]
    value = "\n".join(lines)
    return _EXCESSIVE_BLANK_LINES.sub("\n\n\n", value).strip()


def _repeated_margin_lines(pages: list[str]) -> set[str]:
    counts: Counter[str] = Counter()
    for page in pages:
        nonempty = [line.strip() for line in page.splitlines() if line.strip()]
        margins = set(nonempty[:2] + nonempty[-2:])
        counts.update(line for line in margins if 2 <= len(line) <= 120)
    threshold = max(3, (len(pages) * 3 + 4) // 5)
    return {line for line, count in counts.items() if count >= threshold}


def _remove_margin_lines(page: str, repeated: set[str]) -> str:
    lines = page.splitlines()
    nonempty_indexes = [index for index, line in enumerate(lines) if line.strip()]
    margin_indexes = set(nonempty_indexes[:2] + nonempty_indexes[-2:])
    return "\n".join(
        line
        for index, line in enumerate(lines)
        if not (index in margin_indexes and line.strip() in repeated)
    ).strip()


def _useful_character_ratio(text: str) -> float:
    visible = [character for character in text if not character.isspace()]
    if not visible:
        return 0.0
    useful = sum(
        character.isalnum()
        or "\u4e00" <= character <= "\u9fff"
        or character in "，。；：、,.!?-_/()[]"
        for character in visible
    )
    return useful / len(visible)
