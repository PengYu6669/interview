import re


def clean_question_markdown(value: str) -> str:
    normalized = value.replace("\r\n", "\n").strip()
    normalized = re.sub(r"^```(?:markdown|md)?\s*\n", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\n```\s*$", "", normalized)
    lines = []
    for raw_line in normalized.split("\n"):
        line = raw_line.replace("\t", "    ")
        line = re.sub(r"^(#{1,6})\s*\*\*(.+?)\*\*\s*$", r"\1 \2", line)
        line = re.sub(r"^(#{1,6})([^#\s])", r"\1 \2", line)
        lines.append(line)
    return "\n".join(lines).strip()
