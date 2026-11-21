from datetime import UTC, datetime

import httpx

from job_finder.models import SearchProfile
from job_finder.sources.linkedin import LinkedInPublicJobs


def test_linkedin_public_search_normalizes_cards() -> None:
    html = """
    <html><body><ul><li>
      <div class="base-card" data-entity-urn="urn:li:jobPosting:4492030831">
        <h3 class="base-search-card__title">Python Developer Junior - Remoto</h3>
        <h4 class="base-search-card__subtitle">Acme</h4>
        <span class="job-search-card__location">Brasil</span>
        <time datetime="2026-11-20"></time>
      </div>
    </li></ul></body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["geoId"] == "106057199"
        assert request.url.params["keywords"] == "Python Junior"
        return httpx.Response(200, text=html)

    profile = SearchProfile.model_validate(
        {
            "technologies": ["Python"],
            "seniorities": ["junior"],
            "workModes": ["remote", "hybrid", "onsite"],
            "excludedTerms": [],
            "updatedAt": datetime.now(UTC),
        }
    )
    source = LinkedInPublicJobs(
        request_delay_seconds=0, transport=httpx.MockTransport(handler)
    )
    try:
        result = source.collect(profile, {})
    finally:
        source.close()

    assert result.errors == []
    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "4492030831"
    assert result.jobs[0].source_url == "https://www.linkedin.com/jobs/view/4492030831"
    assert result.jobs[0].seniority == "junior"
    assert result.jobs[0].work_mode == "remote"

