import time
from collections.abc import Iterator
from typing import Any

import httpx

from job_finder.models import NormalizedJob, RunStarted, SourceCursor


def chunks(items: list[NormalizedJob], size: int = 200) -> Iterator[list[NormalizedJob]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class KaliClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 90,
        transport: httpx.BaseTransport | None = None,
    ):
        self.client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "hidekimaesaka/job-finder",
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, path: str, json: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.client.request(method, path, json=json)
                if response.status_code not in {502, 503, 504}:
                    response.raise_for_status()
                    return response
                last_error = httpx.HTTPStatusError(
                    "Backend temporariamente indisponível",
                    request=response.request,
                    response=response,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
        assert last_error is not None
        raise last_error

    def start_run(self, trigger: str) -> RunStarted:
        response = self._request(
            "POST", "/api/internal/v1/job-finder/runs", {"trigger": trigger}
        )
        return RunStarted.model_validate(response.json())

    def ingest(self, run_id: str, jobs: list[NormalizedJob]) -> tuple[int, int]:
        created = 0
        updated = 0
        for batch in chunks(jobs):
            response = self._request(
                "POST",
                f"/api/internal/v1/job-finder/runs/{run_id}/jobs",
                {"items": [item.model_dump(by_alias=True, mode="json") for item in batch]},
            )
            payload = response.json()
            created += int(payload["created"])
            updated += int(payload["updated"])
        return created, updated

    def complete(
        self,
        run_id: str,
        *,
        partial: bool,
        discovered_count: int,
        stats: dict[str, object],
        cursors: list[SourceCursor],
        errors: list[str],
    ) -> None:
        self._request(
            "POST",
            f"/api/internal/v1/job-finder/runs/{run_id}/complete",
            {
                "status": "partial" if partial else "succeeded",
                "discoveredCount": discovered_count,
                "sourceStats": stats,
                "sources": [item.model_dump(by_alias=True, mode="json") for item in cursors],
                "errorSummary": "; ".join(errors)[:500] if errors else None,
            },
        )

    def fail(self, run_id: str, message: str) -> None:
        self._request(
            "POST",
            f"/api/internal/v1/job-finder/runs/{run_id}/fail",
            {"errorSummary": message[:500]},
        )
