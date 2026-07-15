import re
from dataclasses import dataclass
from hashlib import sha256

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CJK = re.compile(r"[\u3400-\u9fff]")
_ASCII_WORD = re.compile(r"[A-Za-z0-9_]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；.!?;])\s*|\n+")


@dataclass(frozen=True, slots=True)
class SemanticChunk:
    index: int
    content: str
    heading_path: tuple[str, ...]
    token_count: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class _Block:
    content: str
    heading_path: tuple[str, ...]
    indivisible: bool = False


def estimate_tokens(text: str) -> int:
    """为切片上限提供稳定估算，不冒充特定厂商的精确 tokenizer。"""

    cjk_count = len(_CJK.findall(text))
    ascii_count = sum(max(1, (len(item) + 3) // 4) for item in _ASCII_WORD.findall(text))
    punctuation_count = sum(1 for item in text if not item.isspace() and not item.isalnum())
    return max(1, cjk_count + ascii_count + (punctuation_count + 3) // 4)


def split_semantic_chunks(
    text: str,
    *,
    target_tokens: int = 450,
    max_tokens: int = 800,
    overlap_tokens: int = 80,
) -> list[SemanticChunk]:
    if target_tokens < 50 or max_tokens < target_tokens or overlap_tokens >= target_tokens:
        raise ValueError("切片参数不合理")
    blocks = _markdown_blocks(text)
    expanded = [piece for block in blocks for piece in _split_oversized_block(block, max_tokens)]
    grouped: list[tuple[str, tuple[str, ...]]] = []
    current: list[_Block] = []
    current_tokens = 0

    for block in expanded:
        block_tokens = estimate_tokens(block.content)
        if current and current_tokens + block_tokens > max_tokens:
            grouped.append((_render_blocks(current), current[-1].heading_path))
            current = _overlap_blocks(current, overlap_tokens)
            current_tokens = sum(estimate_tokens(item.content) for item in current)
        current.append(block)
        current_tokens += block_tokens
        if current_tokens >= target_tokens and not block.indivisible:
            grouped.append((_render_blocks(current), block.heading_path))
            current = _overlap_blocks(current, overlap_tokens)
            current_tokens = sum(estimate_tokens(item.content) for item in current)
    if current:
        rendered = _render_blocks(current)
        if not grouped or rendered != grouped[-1][0]:
            grouped.append((rendered, current[-1].heading_path))

    return [
        SemanticChunk(
            index=index,
            content=content,
            heading_path=heading_path,
            token_count=estimate_tokens(content),
            content_hash=sha256(content.encode("utf-8")).hexdigest(),
        )
        for index, (content, heading_path) in enumerate(grouped)
        if content.strip()
    ]


def _markdown_blocks(text: str) -> list[_Block]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headings: list[str] = []
    blocks: list[_Block] = []
    buffer: list[str] = []
    in_fence = False

    def flush(*, indivisible: bool = False) -> None:
        content = "\n".join(buffer).strip()
        if content:
            blocks.append(
                _Block(
                    content=content,
                    heading_path=tuple(headings),
                    indivisible=indivisible,
                )
            )
        buffer.clear()

    for line in lines:
        heading = _HEADING.match(line) if not in_fence else None
        if heading:
            flush()
            level = len(heading.group(1))
            headings[:] = headings[: level - 1]
            headings.append(heading.group(2).strip())
            blocks.append(_Block(content=line.strip(), heading_path=tuple(headings)))
            continue
        if line.lstrip().startswith("```"):
            if not in_fence:
                flush()
                in_fence = True
            buffer.append(line)
            if in_fence and len(buffer) > 1 and line.lstrip().startswith("```"):
                in_fence = False
                flush(indivisible=True)
            continue
        if in_fence:
            buffer.append(line)
            continue
        if not line.strip():
            flush()
            continue
        buffer.append(line)
    flush(indivisible=in_fence)
    return blocks or [_Block(content=text.strip(), heading_path=())]


def _split_oversized_block(block: _Block, max_tokens: int) -> list[_Block]:
    if estimate_tokens(block.content) <= max_tokens or block.indivisible:
        return [block]
    sentences = [item.strip() for item in _SENTENCE_BOUNDARY.split(block.content) if item.strip()]
    pieces: list[_Block] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}\n{sentence}".strip()
        if current and estimate_tokens(candidate) > max_tokens:
            pieces.append(_Block(current, block.heading_path))
            current = sentence
        else:
            current = candidate
        while estimate_tokens(current) > max_tokens:
            cut = _largest_prefix_within(current, max_tokens)
            pieces.append(_Block(current[:cut].strip(), block.heading_path))
            current = current[cut:].strip()
    if current:
        pieces.append(_Block(current, block.heading_path))
    return pieces


def _largest_prefix_within(text: str, max_tokens: int) -> int:
    low, high = 1, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    return low


def _overlap_blocks(blocks: list[_Block], overlap_tokens: int) -> list[_Block]:
    selected: list[_Block] = []
    total = 0
    for block in reversed(blocks):
        block_tokens = estimate_tokens(block.content)
        if block.indivisible or total + block_tokens > overlap_tokens:
            break
        selected.append(block)
        total += block_tokens
    return list(reversed(selected))


def _render_blocks(blocks: list[_Block]) -> str:
    return "\n\n".join(block.content.strip() for block in blocks if block.content.strip()).strip()
