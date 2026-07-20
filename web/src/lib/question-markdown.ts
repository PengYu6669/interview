export function cleanQuestionMarkdown(value: string) {
  const normalized = value.replace(/\r\n/g, "\n").trim();
  const withoutFence = normalized
    .replace(/^```(?:markdown|md)?\s*\n/i, "")
    .replace(/\n```\s*$/i, "");

  return withoutFence
    .split("\n")
    .map((line) => line
      .replace(/^(#{1,6})\s*\*\*(.+?)\*\*\s*$/, "$1 $2")
      .replace(/^(#{1,6})([^#\s])/, "$1 $2"))
    .join("\n")
    .trim();
}
