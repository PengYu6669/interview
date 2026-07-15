from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

BoardNodeKind = Literal[
    "client",
    "gateway",
    "service",
    "database",
    "cache",
    "queue",
    "external",
    "text",
]
BoardAnnotationKind = Literal["capacity", "note"]


class BoardNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: BoardNodeKind
    label: str = Field(min_length=1, max_length=80)
    x: int = Field(ge=0, le=1_080)
    y: int = Field(ge=0, le=540)
    width: int = Field(ge=120, le=320)
    height: int = Field(ge=56, le=180)


class BoardEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_id: UUID
    target_id: UUID
    label: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def validate_distinct_endpoints(self) -> "BoardEdge":
        if self.source_id == self.target_id:
            raise ValueError("连线不能连接同一个组件")
        return self


class BoardAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: BoardAnnotationKind
    text: str = Field(min_length=1, max_length=240)
    x: int = Field(ge=0, le=1_100)
    y: int = Field(ge=0, le=600)


class BoardState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[BoardNode] = Field(default_factory=list, max_length=40)
    edges: list[BoardEdge] = Field(default_factory=list, max_length=80)
    annotations: list[BoardAnnotation] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def validate_edges_reference_nodes(self) -> "BoardState":
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("组件 ID 不能重复")
        edge_ids = {edge.id for edge in self.edges}
        if len(edge_ids) != len(self.edges):
            raise ValueError("连线 ID 不能重复")
        if any(
            edge.source_id not in node_ids or edge.target_id not in node_ids
            for edge in self.edges
        ):
            raise ValueError("连线必须连接已存在的组件")
        annotation_ids = {annotation.id for annotation in self.annotations}
        if len(annotation_ids) != len(self.annotations):
            raise ValueError("标注 ID 不能重复")
        return self


class BoardSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_snapshot_id: UUID
    base_revision: int = Field(ge=0)
    state: BoardState


class BoardSnapshotData(BaseModel):
    id: UUID
    session_id: UUID
    revision: int = Field(ge=0)
    client_snapshot_id: UUID
    state: BoardState
    created_at: datetime


class BoardConflictData(BaseModel):
    detail: str
    current: BoardSnapshotData
