import logging

from job_finder.config import Settings
from job_finder.kali_client import KaliClient
from job_finder.models import CollectionResult, NormalizedJob
from job_finder.sources.base import JobSource
from job_finder.sources.github import GithubCommunities
from job_finder.sources.gupy import GupyPortal
from job_finder.sources.linkedin import LinkedInPublicJobs

logger = logging.getLogger(__name__)


def _merge_results(results: list[CollectionResult]) -> CollectionResult:
    jobs: dict[tuple[str, str], NormalizedJob] = {}
    cursors = []
    stats: dict[str, object] = {}
    errors: list[str] = []
    for result in results:
        for job in result.jobs:
            jobs[(job.source, job.external_id)] = job
        cursors.extend(result.cursors)
        stats.update(result.stats)
        errors.extend(result.errors)
    return CollectionResult(
        jobs=list(jobs.values()), cursors=cursors, stats=stats, errors=errors
    )


def run(settings: Settings, trigger: str = "scheduled") -> int:
    kali = KaliClient(
        settings.api_url,
        settings.kali_job_finder_token.get_secret_value(),
        timeout=settings.backend_timeout_seconds,
    )
    run_id: str | None = None
    try:
        started = kali.start_run(trigger)
        run_id = started.run_id
        cursors = {item.source: item for item in started.sources}
        sources: list[JobSource] = [
            GithubCommunities(
                settings.github_token.get_secret_value(),
                timeout=settings.request_timeout_seconds,
            ),
            GupyPortal(
                timeout=settings.request_timeout_seconds,
                max_pages_per_term=settings.gupy_max_pages_per_term,
            ),
            LinkedInPublicJobs(
                timeout=settings.request_timeout_seconds,
                request_delay_seconds=settings.linkedin_request_delay_seconds,
            ),
        ]
        results: list[CollectionResult] = []
        for source in sources:
            try:
                results.append(source.collect(started.profile, cursors))
            except Exception as exc:
                logger.exception(
                    "Fonte falhou antes de concluir",
                    extra={"fields": {"source": source.name}},
                )
                results.append(
                    CollectionResult(
                        jobs=[],
                        cursors=[],
                        stats={source.name: {"error": type(exc).__name__}},
                        errors=[f"{source.name}: {type(exc).__name__}"],
                    )
                )
            finally:
                source.close()
        result = _merge_results(results)

        if result.errors and not result.cursors:
            raise RuntimeError("Todas as fontes falharam: " + "; ".join(result.errors))

        created, updated = kali.ingest(run_id, result.jobs) if result.jobs else (0, 0)
        kali.complete(
            run_id,
            partial=bool(result.errors),
            discovered_count=len(result.jobs),
            stats=result.stats,
            cursors=result.cursors,
            errors=result.errors,
        )
        logger.info(
            "Execução concluída",
            extra={
                "fields": {
                    "run_id": run_id,
                    "discovered": len(result.jobs),
                    "created": created,
                    "updated": updated,
                    "partial": bool(result.errors),
                }
            },
        )
        return 2 if result.errors else 0
    except Exception as exc:
        logger.exception("Execução falhou", extra={"fields": {"run_id": run_id}})
        if run_id is not None:
            try:
                kali.fail(run_id, f"{type(exc).__name__}: {exc}")
            except Exception:
                logger.exception(
                    "Não foi possível registrar a falha",
                    extra={"fields": {"run_id": run_id}},
                )
        return 1
    finally:
        kali.close()
