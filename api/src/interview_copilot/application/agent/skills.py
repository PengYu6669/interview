import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=_SKILL_NAME.pattern, max_length=64)
    version: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    training_mode: str = Field(min_length=1, max_length=40)
    instruction_file: str = "SKILL.md"
    rubric_file: str = "rubric.json"


class ActivatedSkill(BaseModel):
    metadata: SkillMetadata
    instructions: str = Field(min_length=1, max_length=30_000)
    rubric: dict


class SkillRegistryError(RuntimeError):
    pass


class SkillRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parents[2] / "agent_skills"

    def list_metadata(self) -> list[SkillMetadata]:
        if not self._root.is_dir():
            raise SkillRegistryError("训练 Skill 目录不存在")
        metadata = [
            self._read_metadata(path)
            for path in sorted(self._root.iterdir())
            if path.is_dir() and (path / "skill.json").is_file()
        ]
        names = [item.name for item in metadata]
        if len(names) != len(set(names)):
            raise SkillRegistryError("训练 Skill 名称重复")
        return metadata

    def activate(self, name: str) -> ActivatedSkill:
        if not _SKILL_NAME.fullmatch(name):
            raise SkillRegistryError("训练 Skill 名称格式不正确")
        skill_dir = self._root / name
        metadata = self._read_metadata(skill_dir)
        if metadata.name != name:
            raise SkillRegistryError("训练 Skill 目录与名称不一致")
        instruction_path = self._safe_child(skill_dir, metadata.instruction_file)
        rubric_path = self._safe_child(skill_dir, metadata.rubric_file)
        try:
            instructions = _read_skill_instructions(instruction_path)
            rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SkillRegistryError(f"训练 Skill {name} 内容无法读取") from exc
        if not isinstance(rubric, dict):
            raise SkillRegistryError(f"训练 Skill {name} 的评价标准格式不正确")
        return ActivatedSkill(metadata=metadata, instructions=instructions, rubric=rubric)

    def _read_metadata(self, skill_dir: Path) -> SkillMetadata:
        try:
            payload = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
            return SkillMetadata.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise SkillRegistryError(f"训练 Skill 元数据无效：{skill_dir.name}") from exc

    @staticmethod
    def _safe_child(parent: Path, relative_name: str) -> Path:
        candidate = (parent / relative_name).resolve()
        try:
            candidate.relative_to(parent.resolve())
        except ValueError as exc:
            raise SkillRegistryError("训练 Skill 文件路径越界") from exc
        if not candidate.is_file():
            raise SkillRegistryError(f"训练 Skill 缺少文件：{relative_name}")
        return candidate


def _read_skill_instructions(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return text
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return text
    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise SkillRegistryError(f"训练 Skill {path.parent.name} 正文为空")
    return body

