from typing import Protocol

from job_finder.models import CollectionResult, SearchProfile, SourceCursor


class JobSource(Protocol):
    name: str

    def collect(
        self, profile: SearchProfile, cursors: dict[str, SourceCursor]
    ) -> CollectionResult: ...
