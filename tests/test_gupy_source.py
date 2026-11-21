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
                            "description": "APIs em Python com apoio de profissionais sênior.",
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
                        {
                            "id": 103,
                            "name": "Desenvolvedor Python Pleno",
                            "description": "APIs em Python.",
                            "careerPageName": "Distante",
                            "publishedDate": "2026-11-21T08:00:00Z",
                            "applicationDeadline": "2026-12-31T00:00:00Z",
                            "workplaceType": "on-site",
                            "city": "Ribeirão Preto",
                            "state": "São Paulo",
                            "jobUrl": "https://distante.gupy.io/job/103",
                        },
                    ],
                    "pagination": {"total": 3, "limit": 12, "offset": 0},
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
    assert {job.external_id for job in result.jobs} == {"101", "102"}
    sao_paulo = next(job for job in result.jobs if job.external_id == "101")
    campinas = next(job for job in result.jobs if job.external_id == "102")
    assert sao_paulo.company == "Acme"
    assert sao_paulo.work_mode == "hybrid"
    assert sao_paulo.location == "São Paulo, São Paulo"
    assert campinas.location == "Campinas, São Paulo"


def test_gupy_imports_explicit_job_url_without_automatic_match() -> None:
    job_url = (
        "https://acme.gupy.io/job/"
        "eyJqb2JJZCI6MTIzLCJzb3VyY2UiOiJndXB5X3BvcnRhbCJ9="
        "?jobBoardSource=gupy_portal"
    )
    payload = {
        "props": {
            "pageProps": {
                "job": {
                    "id": 123,
                    "name": "Pessoa Desenvolvedora Backend Pleno",
                    "description": "Serviços em Node.js e TypeScript.",
                    "responsibilities": "Construir APIs.",
                    "prerequisites": "Experiência com SQL.",
                    "relevantExperiences": "",
                    "careerPage": {"name": "Acme"},
                    "publishedAt": "2026-11-21T10:00:00Z",
                    "expiresAt": "2026-12-31",
                    "workplaceType": "remote",
                    "addressCity": "",
                    "addressState": "",
                    "status": "published",
                },
                "canonicalUrl": "https://acme.gupy.io/jobs/123",
            }
        }
    }
    html = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "portal.gupy.io":
            empty = {
                "props": {
                    "pageProps": {
                        "initialJobList": {
                            "data": [],
                            "pagination": {"total": 0},
                        }
                    }
                }
            }
            return httpx.Response(
                200,
                text=(
                    '<script id="__NEXT_DATA__" type="application/json">'
                    + json.dumps(empty)
                    + "</script>"
                ),
            )
        assert str(request.url) == job_url
        return httpx.Response(200, text=html)

    profile = SearchProfile.model_validate(
        {
            "technologies": ["Python", "Java"],
            "seniorities": ["junior", "mid"],
            "workModes": ["remote", "hybrid", "onsite"],
            "excludedTerms": [],
            "updatedAt": datetime.now(UTC),
        }
    )
    source = GupyPortal(
        max_pages_per_term=1,
        manual_urls=[job_url, job_url],
        transport=httpx.MockTransport(handler),
    )
    try:
        result = source.collect(profile, {})
    finally:
        source.close()

    assert result.errors == []
    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "123"
    assert result.jobs[0].company == "Acme"
    assert result.jobs[0].seniority == "mid"
    assert result.jobs[0].work_mode == "remote"
    assert result.jobs[0].technologies == []
    assert result.jobs[0].application_url == job_url
    assert result.stats["gupy:manual"] == {
        "requested": 2,
        "fetched": 2,
        "imported": 2,
    }

