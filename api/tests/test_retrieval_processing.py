from interview_copilot.application.retrieval.chunking import (
    estimate_tokens,
    split_semantic_chunks,
)
from interview_copilot.application.retrieval.normalization import normalize_document_text
from interview_copilot.application.retrieval.structure import recover_document_structure


def test_normalization_removes_repeated_page_margins_and_reports_garbage() -> None:
    pages = [
        f"候选人简历\n第 {index} 页\n项目 {index}\n负责核心接口设计\n公司内部资料"
        for index in range(1, 5)
    ]
    pages[2] += "\n�"

    result = normalize_document_text("\n\n".join(pages), pages=pages)

    assert "候选人简历" not in result.text
    assert "公司内部资料" not in result.text
    assert "项目 3" in result.text
    assert any("页眉或页脚" in warning for warning in result.warnings)
    assert any("乱码" in warning for warning in result.warnings)


def test_semantic_chunks_keep_heading_context_and_code_block_intact() -> None:
    document = (
        """# RAG 项目

## 检索链路

使用向量召回和关键词召回。需要保留来源，并对结果进行融合。

```python
def retrieve(query: str) -> list[str]:
    return [query]
```

## 评测

"""
        + "召回结果需要人工标注。" * 120
    )

    chunks = split_semantic_chunks(document, target_tokens=80, max_tokens=140, overlap_tokens=20)

    assert len(chunks) > 2
    assert all(chunk.token_count <= 140 for chunk in chunks if "```python" not in chunk.content)
    code_chunks = [chunk for chunk in chunks if "```python" in chunk.content]
    assert len(code_chunks) == 1
    assert code_chunks[0].content.count("```") == 2
    assert any(chunk.heading_path[-1:] == ("评测",) for chunk in chunks)
    assert all(len(chunk.content_hash) == 64 for chunk in chunks)
    assert estimate_tokens("中文 RAG retrieval") > 4


def test_chunker_rejects_invalid_limits() -> None:
    try:
        split_semantic_chunks("内容", target_tokens=40)
    except ValueError as exc:
        assert "参数" in str(exc)
    else:
        raise AssertionError("不合理切片参数必须被拒绝")


def test_structure_recovery_handles_questions_navigation_and_plain_text() -> None:
    text = """目录
Q1 第一题 ................................ 3
Q2 第二题 ................................ 5
- 3 -
Q1：如何设计限流体系？
【一句话定位】
限流要同时控制平均流量和突发流量。
这是一段没有标题的普通正文，不应被改写。
"""

    result = recover_document_structure(text)

    assert "## Q1：如何设计限流体系？" in result.text
    assert "### 【一句话定位】" in result.text
    assert "这是一段没有标题的普通正文" in result.text
    assert "........" not in result.text
    assert result.high_confidence_headings == ("Q1：如何设计限流体系？",)


def test_unstructured_long_text_still_uses_overlapping_semantic_windows() -> None:
    text = "这是没有标题的连续技术说明。" * 300

    chunks = split_semantic_chunks(text, target_tokens=100, max_tokens=160, overlap_tokens=30)

    assert len(chunks) > 10
    assert all(chunk.heading_path == () for chunk in chunks)
    assert all(chunk.token_count <= 160 for chunk in chunks)
