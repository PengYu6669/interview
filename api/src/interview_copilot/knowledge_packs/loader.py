import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class KnowledgeSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1, max_length=100)
    url: HttpUrl


class KnowledgePackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,60}$")
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    updated_at: date
    filename: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*\.md$")
    sources: list[KnowledgeSource] = Field(min_length=1, max_length=20)


@dataclass(frozen=True, slots=True)
class KnowledgePack:
    manifest: KnowledgePackManifest
    content: str


def load_knowledge_packs(base_path: Path | None = None) -> list[KnowledgePack]:
    root = (base_path or Path(__file__).parent).resolve()
    manifest_path = root / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifests = [KnowledgePackManifest.model_validate(item) for item in raw]
    if len({item.id for item in manifests}) != len(manifests):
        raise ValueError("知识包 ID 不能重复")

    packs: list[KnowledgePack] = []
    for manifest in manifests:
        content_path = (root / manifest.filename).resolve()
        if content_path.parent != root:
            raise ValueError("知识包文件必须位于知识包目录")
        content = content_path.read_text(encoding="utf-8").strip()
        if len(content) < 200:
            raise ValueError(f"知识包 {manifest.id} 内容过短")
        packs.append(KnowledgePack(manifest=manifest, content=content))
    return packs
