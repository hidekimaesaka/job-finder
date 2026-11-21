from datetime import UTC, datetime

import httpx

from job_finder.models import SearchProfile
from job_finder.sources.github import REPOSITORIES, GithubCommunities


def test_github_communities_normalizes_matching_issues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        repository = "/".join(request.url.path.split("/")[2:4])
        if repository == "backend-br/vagas":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 42,
                        "title": "[Remoto] Pessoa Desenvolvedora Python Júnior na Acme",
                        "body": "API com Python e PostgreSQL.",
                        "labels": [{"name": "Júnior"}, {"name": "Remoto"}],
                        "html_url": "https://github.com/backend-br/vagas/issues/42",
                        "created_at": "2026-11-20T10:00:00Z",
                        "updated_at": "2026-11-21T10:00:00Z",
                        "state": "open",
                    }
                ],
            )
        return httpx.Response(200, json=[])

    profile = SearchProfile.model_validate(
        {
            "technologies": ["Python", "React"],
            "seniorities": ["junior", "mid"],
            "workModes": ["remote", "hybrid", "onsite"],
            "excludedTerms": [],
            "updatedAt": datetime.now(UTC),
        }
    )
    source = GithubCommunities("token", transport=httpx.MockTransport(handler))
    try:
        result = source.collect(profile, {})
    finally:
        source.close()

    assert result.errors == []
    assert len(result.cursors) == len(REPOSITORIES)
    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "42"
    assert result.jobs[0].company == "Acme"
    assert result.jobs[0].location == "Remoto"
    assert result.jobs[0].technologies == ["Python"]
