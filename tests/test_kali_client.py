import json

import httpx

from job_finder.kali_client import KaliClient, chunks
from job_finder.models import NormalizedJob


def test_chunks_preserve_all_items() -> None:
    jobs = [
        NormalizedJob(source="github:test", externalId=str(index), title="Vaga", sourceUrl="x")
        for index in range(401)
    ]
    assert [len(batch) for batch in chunks(jobs)] == [200, 200, 1]


def test_kali_client_uses_camel_case_contract() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else {}
        requests.append(payload)
        if request.url.path.endswith("/runs"):
            return httpx.Response(
                201,
                json={
                    "runId": "run-1",
                    "profile": {
                        "technologies": ["Python"],
                        "seniorities": ["junior"],
                        "workModes": ["remote"],
                        "excludedTerms": [],
                        "updatedAt": "2026-11-21T10:00:00Z",
                    },
                    "sources": [],
                },
            )
        return httpx.Response(200, json={"created": 1, "updated": 0})

    client = KaliClient("https://kali.example", "secret", transport=httpx.MockTransport(handler))
    try:
        started = client.start_run("manual")
        client.ingest(
            started.run_id,
            [
                NormalizedJob(
                    source="github:test", externalId="1", title="Python", sourceUrl="https://x"
                )
            ],
        )
    finally:
        client.close()

    assert requests[0] == {"trigger": "manual"}
    assert requests[1]["items"][0]["externalId"] == "1"  # type: ignore[index]
