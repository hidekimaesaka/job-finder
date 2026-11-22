import logging
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from job_finder.matching import detect_seniority, evaluate, normalize_text
from job_finder.models import CollectionResult, NormalizedJob, SearchProfile, SourceCursor

logger = logging.getLogger(__name__)

SENIORITY_TERMS = {"junior": "Junior", "mid": "Pleno"}


def _text(card: Tag, selector: str) -> str:
    element = card.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


class LinkedInPublicJobs:
    name = "linkedin"

    def __init__(
        self,
        timeout: float = 30,
        request_delay_seconds: float = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        self.request_delay_seconds = request_delay_seconds
        self.client = httpx.Client(
            base_url="https://br.linkedin.com",
            headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
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

    def _request(self, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(4):
            response: httpx.Response | None = None
            try:
                response = self.client.get("/jobs/search/", params=params)
                if response.status_code < 500 and response.status_code not in {403, 429, 999}:
                    response.raise_for_status()
                    return response
                last_error = httpx.HTTPStatusError(
                    "LinkedIn temporariamente indisponível",
                    request=response.request,
                    response=response,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            if attempt < 3:
                retry_after = response.headers.get("Retry-After") if response else None
                delay = (
                    min(float(retry_after), 60)
                    if retry_after and retry_after.isdigit()
                    else 5 * 2**attempt
                )
                logger.warning(
                    "LinkedIn limitou a consulta; nova tentativa agendada",
                    extra={"fields": {"attempt": attempt + 1, "delay_seconds": delay}},
                )
                time.sleep(delay)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _cards(response: httpx.Response) -> list[Tag]:
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select('[data-entity-urn^="urn:li:jobPosting:"]')
        if not cards and "no-results" not in response.text:
            raise ValueError("LinkedIn não retornou cartões de vagas")
        return [card for card in cards if isinstance(card, Tag)]

    def collect(
        self, profile: SearchProfile, cursors: dict[str, SourceCursor]
    ) -> CollectionResult:
        del cursors  # Revalida a janela pública de sete dias e usa upsert no backend.
        jobs: dict[str, NormalizedJob] = {}
        next_cursors: list[SourceCursor] = []
        stats: dict[str, object] = {}
        errors: list[str] = []
        query_number = 0

        for technology in profile.technologies:
            for seniority in profile.seniorities:
                seniority_term = SENIORITY_TERMS[seniority]
                cursor_name = (
                    f"linkedin:public:{technology.casefold()}:{seniority.casefold()}"
                )
                try:
                    if query_number and self.request_delay_seconds:
                        time.sleep(self.request_delay_seconds)
                    query_number += 1
                    response = self._request(
                        {
                            "keywords": f"{technology} {seniority_term}",
                            "location": "Brasil",
                            "geoId": "106057199",
                            "f_TPR": "r604800",
                        }
                    )
                    cards = self._cards(response)
                    matched = 0
                    latest: datetime | None = None
                    for card in cards:
                        urn = str(card.get("data-entity-urn") or "")
                        external_id = urn.rsplit(":", 1)[-1]
                        title = _text(card, ".base-search-card__title")
                        company = _text(card, ".base-search-card__subtitle") or None
                        location = _text(card, ".job-search-card__location") or None
                        if not external_id.isdigit() or not title:
                            continue
                        time_element = card.select_one("time[datetime]")
                        published = None
                        if isinstance(time_element, Tag):
                            value: Any = time_element.get("datetime")
                            if value:
                                published = datetime.fromisoformat(
                                    str(value).replace("Z", "+00:00")
                                )
                        visible_text = "\n".join((title, company or "", location or ""))
                        inferred_seniority = detect_seniority(normalize_text(visible_text))
                        query_seniority = (
                            seniority_term if inferred_seniority == "unknown" else ""
                        )
                        text = "\n".join(
                            (visible_text, technology, query_seniority)
                        )
                        match = evaluate(text, profile, location=location)
                        if match is None:
                            continue
                        latest = (
                            max(latest, published)
                            if latest and published
                            else published or latest
                        )
                        url = f"https://www.linkedin.com/jobs/view/{external_id}"
                        jobs[external_id] = NormalizedJob(
                            source=self.name,
                            external_id=external_id,
                            title=title,
                            company=company,
                            source_url=url,
                            application_url=url,
                            location=location,
                            work_mode=match.work_mode,
                            seniority=match.seniority,
                            technologies=match.technologies,
                            matched_terms=match.matched_terms,
                            published_at=published,
                            source_updated_at=published,
                        )
                        matched += 1
                    next_cursors.append(SourceCursor(source=cursor_name, cursor=latest))
                    stats[cursor_name] = {"fetched": len(cards), "matched": matched}
                except Exception as exc:
                    errors.append(f"{cursor_name}: {type(exc).__name__}")
                    stats[cursor_name] = {"error": type(exc).__name__}
                    logger.exception(
                        "Falha ao consultar LinkedIn",
                        extra={"fields": {"source": cursor_name}},
                    )

        return CollectionResult(
            jobs=list(jobs.values()), cursors=next_cursors, stats=stats, errors=errors
        )
