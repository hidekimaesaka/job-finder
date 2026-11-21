import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from job_finder.matching import evaluate, extract_company, extract_location
from job_finder.models import CollectionResult, NormalizedJob, SearchProfile, SourceCursor

logger = logging.getLogger(__name__)

REPOSITORIES = (
    "backend-br/vagas",
    "frontendbr/vagas",
    "pydevbr/vagas",
    "soujava/vagas-java",
    "react-brasil/vagas",
)


class GithubCommunities:
    name = "github-communities"

    def __init__(
        self,
        token: str,
        timeout: float = 30,
        transport: httpx.BaseTransport | None = None,
    ):
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "hidekimaesaka/job-finder",
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, url: str, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url, params=params)
                if response.status_code < 500 and response.status_code not in {403, 429}:
                    response.raise_for_status()
                    return response
                if response.status_code in {403, 429} and response.headers.get(
                    "x-ratelimit-remaining"
                ) != "0":
                    response.raise_for_status()
                retry_after = min(int(response.headers.get("retry-after", "2")), 30)
                last_error = httpx.HTTPStatusError(
                    "GitHub temporariamente indisponível",
                    request=response.request,
                    response=response,
                )
                time.sleep(retry_after if attempt == 2 else 2**attempt)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        assert last_error is not None
        raise last_error

    def _issues(
        self, repository: str, cursor: SourceCursor | None
    ) -> tuple[list[dict[str, Any]], datetime]:
        since = (
            cursor.cursor
            if cursor and cursor.cursor
            else datetime.now(UTC) - timedelta(days=90)
        )
        params = {
            "state": "all" if cursor and cursor.cursor else "open",
            "sort": "updated",
            "direction": "asc",
            "per_page": "100",
            "since": since.isoformat().replace("+00:00", "Z"),
        }
        issues: list[dict[str, Any]] = []
        latest = since
        for page in range(1, 6):
            params["page"] = str(page)
            response = self._request(f"/repos/{repository}/issues", params)
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError(f"Resposta inesperada do GitHub para {repository}")
            for item in batch:
                if isinstance(item, dict) and "pull_request" not in item:
                    issues.append(item)
                    updated = datetime.fromisoformat(str(item["updated_at"]).replace("Z", "+00:00"))
                    latest = max(latest, updated)
            if len(batch) < 100:
                break
        return issues, latest

    def collect(
        self, profile: SearchProfile, cursors: dict[str, SourceCursor]
    ) -> CollectionResult:
        jobs: list[NormalizedJob] = []
        next_cursors: list[SourceCursor] = []
        stats: dict[str, object] = {}
        errors: list[str] = []

        for repository in REPOSITORIES:
            source = f"github:{repository}"
            try:
                issues, latest = self._issues(repository, cursors.get(source))
                matched = 0
                for issue in issues:
                    title = str(issue.get("title") or "")
                    body = str(issue.get("body") or "")
                    location = extract_location(title)
                    labels = " ".join(
                        str(label.get("name") or "")
                        for label in issue.get("labels", [])
                        if isinstance(label, dict)
                    )
                    match = evaluate(
                        "\n".join((title, labels, body)), profile, location=location
                    )
                    if match is None:
                        continue
                    matched += 1
                    jobs.append(
                        NormalizedJob(
                            source=source,
                            external_id=str(issue["number"]),
                            title=title,
                            company=extract_company(title),
                            source_url=str(issue["html_url"]),
                            location=location,
                            work_mode=match.work_mode,
                            seniority=match.seniority,
                            technologies=match.technologies,
                            matched_terms=match.matched_terms,
                            published_at=datetime.fromisoformat(
                                str(issue["created_at"]).replace("Z", "+00:00")
                            ),
                            source_updated_at=datetime.fromisoformat(
                                str(issue["updated_at"]).replace("Z", "+00:00")
                            ),
                            closed=issue.get("state") == "closed",
                        )
                    )
                next_cursors.append(SourceCursor(source=source, cursor=latest))
                stats[source] = {"fetched": len(issues), "matched": matched}
                logger.info(
                    "Fonte consultada",
                    extra={
                        "fields": {
                            "source": source,
                            "fetched": len(issues),
                            "matched": matched,
                        }
                    },
                )
            except Exception as exc:
                errors.append(f"{source}: {type(exc).__name__}")
                stats[source] = {"error": type(exc).__name__}
                logger.exception("Falha ao consultar fonte", extra={"fields": {"source": source}})

        return CollectionResult(jobs=jobs, cursors=next_cursors, stats=stats, errors=errors)
