from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VisualType = Literal["timeline", "flowchart", "concept_map", "comparison", "process", "cause_effect"]
Language = Literal["english", "hindi", "punjabi"]


class RoadmapSource(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=80)
    source_type: Literal["pdf", "web"] = "pdf"
    document: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    publisher: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    retrieved_at: datetime | None = None
    source_category: str | None = Field(default=None, max_length=80)
    trust_level: str | None = Field(default=None, max_length=32)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    chunk_id: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_provenance(self):
        if self.source_type == "pdf" and not (self.document or self.title):
            raise ValueError("PDF source requires a document name")
        if self.source_type == "web" and not (self.title and self.url and self.publisher):
            raise ValueError("Web source requires title, URL, and publisher")
        return self


class RoadmapNode(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=40)
    label: str = Field(min_length=1, max_length=90)
    year: str | None = Field(default=None, max_length=24, pattern=r"^[0-9A-Za-z .,/\-–—]+$")
    description: str = Field(min_length=1, max_length=280)
    importance: str = Field(default="", max_length=220)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class RoadmapConnection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_id: str = Field(alias="from", max_length=40)
    to: str = Field(max_length=40)
    label: str = Field(default="", max_length=60)


class RoadmapStructure(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    visual_type: VisualType
    summary: str = Field(min_length=1, max_length=360)
    nodes: list[RoadmapNode] = Field(min_length=1, max_length=12)
    connections: list[RoadmapConnection] = Field(default_factory=list, max_length=24)
    exam_points: list[str] = Field(default_factory=list, max_length=8)
    sources: list[RoadmapSource] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_references(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node IDs must be unique")
        known_nodes = set(node_ids)
        for connection in self.connections:
            if connection.from_id not in known_nodes or connection.to not in known_nodes:
                raise ValueError("Connections must reference valid node IDs")
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source IDs must be unique")
        known_sources = set(source_ids)
        for node in self.nodes:
            if not set(node.source_ids).issubset(known_sources):
                raise ValueError("Node source IDs must reference listed retrieved sources")
        return self


class VisualRoadmapCreate(BaseModel):
    topic: str = Field(min_length=2, max_length=255)
    visual_type: VisualType
    language: Language = "english"
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class VisualRoadmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; status: Literal["generating", "ready", "failed"]; title: str
    subject: str; topic: str; visual_type: VisualType; language: Language
    conversation_id: str | None; structure: RoadmapStructure; sources: list[RoadmapSource]
    svg_url: str; created_at: datetime; updated_at: datetime
