from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SearchProfile(ApiModel):
    technologies: list[str]
    seniorities: list[Literal["junior", "mid"]]
    work_modes: list[Literal["remote", "hybrid", "onsite"]]
    excluded_terms: list[str]
    updated_at: datetime


class SourceCursor(ApiModel):
    source: str
    cursor: datetime | None = None
    etag: str | None = None


class RunStarted(ApiModel):
    run_id: str
    profile: SearchProfile
    sources: list[SourceCursor]


class NormalizedJob(ApiModel):
    source: str
    external_id: str
    title: str
    company: str | None = None
    source_url: str
    application_url: str | None = None
    location: str | None = None
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    seniority: Literal["junior", "mid", "senior", "unknown"] = "unknown"
    technologies: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    closed: bool = False


class CollectionResult(BaseModel):
    jobs: list[NormalizedJob]
    cursors: list[SourceCursor]
    stats: dict[str, object]
    errors: list[str]
