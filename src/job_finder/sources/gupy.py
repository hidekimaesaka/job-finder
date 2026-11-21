import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from job_finder.matching import evaluate
from job_finder.models import CollectionResult, NormalizedJob, SearchProfile, SourceCursor

logger = logging.getLogger(__name__)


def _as_datetime(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _work_mode(value: object) -> tuple[str, str]:
    normalized = str(value or "").casefold()
    modes = {
        "remote": ("remote", "remoto"),
        "hybrid": ("hybrid", "hibrido"),
        "on-site": ("onsite", "presencial"),
        "onsite": ("onsite", "presencial"),
    }
    return modes.get(normalized, ("unknown", ""))


class GupyPortal:
    name = "gupy"

    def __init__(
        self,
        timeout: float = 30,
        max_pages_per_term: int = 5,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_pages_per_term = max_pages_per_term
        self.client = httpx.Client(
            base_url="https://portal.gupy.io",
            headers={
                "Accept-Language": "pt-BR,pt;q=0.9",
                "User-Agent": (
                    "hidekimaesaka/job-finder/0.2 "
                    "(+https://github.com/hidekimaesaka/job-finder)"
                ),
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(path, params=params)
                if response.status_code < 500 and response.status_code != 429:
                    response.raise_for_status()
                    return response
                last_error = httpx.HTTPStatusError(
                    "Gupy temporariamente indisponível",
                    request=response.request,
                    response=response,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _page_data(response: httpx.Response) -> tuple[list[dict[str, Any]], int]:
        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script is None or script.string is None:
            raise ValueError("Gupy não retornou __NEXT_DATA__")
        payload = json.loads(script.string)
        listing = payload["props"]["pageProps"]["initialJobList"]
        data = listing["data"]
        if not isinstance(data, list):
            raise ValueError("Lista de vagas da Gupy inválida")
        return [item for item in data if isinstance(item, dict)], int(
            listing["pagination"]["total"]
        )

    def collect(
        self, profile: SearchProfile, cursors: dict[str, SourceCursor]
    ) -> CollectionResult:
        del cursors  # A busca pública é revalidada; o backend resolve idempotência.
        jobs: dict[str, NormalizedJob] = {}
        next_cursors: list[SourceCursor] = []
        stats: dict[str, object] = {}
        errors: list[str] = []

        for technology in profile.technologies:
            cursor_name = f"gupy:portal:{technology.casefold()}"
            fetched = 0
            matched = 0
            latest: datetime | None = None
            try:
                route = f"/job-search/{quote(f'term={technology}', safe='')}"
                for page in range(1, self.max_pages_per_term + 1):
                    response = self._request(route, {"page": str(page)})
                    items, total = self._page_data(response)
                    fetched += len(items)
                    for item in items:
                        external_id = str(item.get("id") or "")
                        title = str(item.get("name") or "").strip()
                        source_url = str(item.get("jobUrl") or "").strip()
                        if not external_id or not title or not source_url:
                            continue
                        description = BeautifulSoup(
                            str(item.get("description") or ""), "html.parser"
                        ).get_text(" ", strip=True)
                        detected_mode, mode_term = _work_mode(item.get("workplaceType"))
                        company = str(item.get("careerPageName") or "").strip() or None
                        city = str(item.get("city") or "").strip()
                        state = str(item.get("state") or "").strip()
                        location = ", ".join(value for value in (city, state) if value) or None
                        text = "\n".join((title, company or "", mode_term, description))
                        match = evaluate(text, profile, location=location)
                        if match is None:
                            continue
                        published = _as_datetime(item.get("publishedDate"))
                        latest = (
                            max(latest, published)
                            if latest and published
                            else published or latest
                        )
                        deadline = _as_datetime(item.get("applicationDeadline"))
                        closed = bool(deadline and deadline < datetime.now(UTC))
                        jobs[external_id] = NormalizedJob(
                            source=self.name,
                            external_id=external_id,
                            title=title,
                            company=company,
                            source_url=source_url,
                            application_url=source_url,
                            location=location,
                            work_mode=detected_mode,
                            seniority=match.seniority,
                            technologies=match.technologies,
                            matched_terms=match.matched_terms,
                            published_at=published,
                            source_updated_at=published,
                            closed=closed,
                        )
                        matched += 1
                    if fetched >= total or not items:
                        break
                next_cursors.append(SourceCursor(source=cursor_name, cursor=latest))
                stats[cursor_name] = {"fetched": fetched, "matched": matched}
            except Exception as exc:
                errors.append(f"{cursor_name}: {type(exc).__name__}")
                stats[cursor_name] = {"error": type(exc).__name__}
                logger.exception(
                    "Falha ao consultar Gupy",
                    extra={"fields": {"source": cursor_name}},
                )

        return CollectionResult(
            jobs=list(jobs.values()), cursors=next_cursors, stats=stats, errors=errors
        )
