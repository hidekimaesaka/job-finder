import json
from datetime import UTC, datetime

import httpx

from job_finder.models import SearchProfile
from job_finder.sources.gupy import GupyPortal


def test_gupy_normalizes_jobs_and_applies_location_rule() -> None:
    payload = {
        "props": {
            "pageProps": {
                "initialJobList": {
                    "data": [
                        {
                            "id": 101,
                            "name": "Desenvolvedor Python Pleno",
                            "description": "APIs em Python.",
                            "careerPageName": "Acme",
                            "publishedDate": "2026-11-21T10:00:00Z",
                            "applicationDeadline": "2026-12-31T00:00:00Z",
                            "workplaceType": "hybrid",
                            "city": "São Paulo",
                            "state": "São Paulo",
                            "jobUrl": "https://acme.gupy.io/job/101",
                        },
                        {
                            "id": 102,
                            "name": "Desenvolvedor Python Pleno",
                            "description": "APIs em Python.",
                            "careerPageName": "Outra",
                            "publishedDate": "2026-11-21T09:00:00Z",
                            "applicationDeadline": "2026-12-31T00:00:00Z",
                            "workplaceType": "on-site",
                            "city": "Campinas",
                            "state": "São Paulo",
                            "jobUrl": "https://outra.gupy.io/job/102",
                        },
                    ],
                    "pagination": {"total": 2, "limit": 12, "offset": 0},
                }
            }
        }
    }
    html = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "term%3DPython" in str(request.url)
        return httpx.Response(200, text=html)

    profile = SearchProfile.model_validate(
        {
            "technologies": ["Python"],
            "seniorities": ["mid"],
            "workModes": ["remote", "hybrid", "onsite"],
            "excludedTerms": [],
            "updatedAt": datetime.now(UTC),
        }
    )
    source = GupyPortal(max_pages_per_term=1, transport=httpx.MockTransport(handler))
    try:
        result = source.collect(profile, {})
    finally:
        source.close()

    assert result.errors == []
    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "101"
    assert result.jobs[0].company == "Acme"
    assert result.jobs[0].work_mode == "hybrid"
    assert result.jobs[0].location == "São Paulo, São Paulo"

