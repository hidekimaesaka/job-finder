import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

from job_finder.matching import (
    detect_seniority,
    detect_work_mode,
    evaluate,
    normalize_text,
    technology_matches,
)
from job_finder.models import CollectionResult, NormalizedJob, SearchProfile, SourceCursor

logger = logging.getLogger(__name__)


def _as_datetime(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _as_deadline(value: object) -> datetime | None:
    parsed = _as_datetime(value)
    if parsed is not None and len(str(value)) == 10:
        return parsed + timedelta(days=1)
    return parsed


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
        manual_urls: list[str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_pages_per_term = max_pages_per_term
        self.manual_urls = manual_urls or []
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

    def _request(
        self, path: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
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

    @staticmethod
    def _job_data(response: httpx.Response) -> tuple[dict[str, Any], str | None]:
        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script is None or script.string is None:
            raise ValueError("Gupy não retornou __NEXT_DATA__")
        page_props = json.loads(script.string)["props"]["pageProps"]
        job = page_props["job"]
        if not isinstance(job, dict):
            raise ValueError("Vaga da Gupy inválida")
        canonical_url = page_props.get("canonicalUrl")
        return job, str(canonical_url) if canonical_url else None

    @staticmethod
    def _validate_manual_url(url: str) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold()
        valid = (
            parsed.scheme == "https"
            and hostname.endswith(".gupy.io")
            and "/job/" in parsed.path
        )
        if not valid:
            raise ValueError("URL manual deve apontar para uma vaga pública em *.gupy.io")

    def _manual_job(
        self,
        item: dict[str, Any],
        requested_url: str,
        canonical_url: str | None,
        profile: SearchProfile,
    ) -> NormalizedJob:
        external_id = str(item.get("id") or "")
        title = str(item.get("name") or "").strip()
        if not external_id or not title:
            raise ValueError("Vaga manual da Gupy sem ID ou título")

        career_page = item.get("careerPage")
        company = (
            str(career_page.get("name") or "").strip()
            if isinstance(career_page, dict)
            else ""
        ) or None
        description = BeautifulSoup(
            " ".join(
                str(item.get(field) or "")
                for field in (
                    "description",
                    "responsibilities",
                    "prerequisites",
                    "relevantExperiences",
                )
            ),
            "html.parser",
        ).get_text(" ", strip=True)
        detected_mode, mode_term = _work_mode(item.get("workplaceType"))
        city = str(item.get("addressCity") or "").strip()
        state = str(item.get("addressState") or "").strip()
        location = ", ".join(value for value in (city, state) if value) or None
        text = "\n".join((title, company or "", mode_term, description))
        normalized = normalize_text(text)
        technologies, matched_terms = technology_matches(normalized, profile.technologies)
        seniority = detect_seniority(normalize_text(title))
        if seniority == "unknown":
            seniority = detect_seniority(normalized)
        work_mode = detected_mode if detected_mode != "unknown" else detect_work_mode(normalized)
        published = _as_datetime(item.get("publishedAt"))
        deadline = _as_deadline(
            item.get("expiresAt") or item.get("registerEndDate")
        )
        closed = str(item.get("status") or "").casefold() != "published" or bool(
            deadline and deadline < datetime.now(UTC)
        )
        source_url = canonical_url or requested_url
        return NormalizedJob(
            source=self.name,
            external_id=external_id,
            title=title,
            company=company,
            source_url=source_url,
            application_url=requested_url,
            location=location,
            work_mode=work_mode,
            seniority=seniority,
            technologies=technologies,
            matched_terms=matched_terms,
            published_at=published,
            source_updated_at=published,
            closed=closed,
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
                        title_seniority = detect_seniority(normalize_text(title))
                        match = evaluate(
                            text,
                            profile,
                            location=location,
                            seniority_hint=(
                                title_seniority if title_seniority != "unknown" else None
                            ),
                        )
                        if match is None:
                            continue
                        published = _as_datetime(item.get("publishedDate"))
                        latest = (
                            max(latest, published)
                            if latest and published
                            else published or latest
                        )
                        deadline = _as_deadline(item.get("applicationDeadline"))
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

        manual_source = "gupy:manual"
        manual_fetched = 0
        manual_imported = 0
        for url in self.manual_urls:
            try:
                self._validate_manual_url(url)
                response = self._request(url)
                item, canonical_url = self._job_data(response)
                manual_fetched += 1
                job = self._manual_job(item, url, canonical_url, profile)
                jobs[job.external_id] = job
                manual_imported += 1
            except Exception as exc:
                errors.append(f"{manual_source}:{url}: {type(exc).__name__}")
                logger.exception(
                    "Falha ao importar URL da Gupy",
                    extra={"fields": {"source": manual_source, "url": url}},
                )
        if self.manual_urls:
            stats[manual_source] = {
                "requested": len(self.manual_urls),
                "fetched": manual_fetched,
                "imported": manual_imported,
            }

        return CollectionResult(
            jobs=list(jobs.values()), cursors=next_cursors, stats=stats, errors=errors
        )
