from datetime import UTC, datetime

from job_finder.matching import detect_seniority, evaluate, normalize_text
from job_finder.models import SearchProfile


def profile(**changes: object) -> SearchProfile:
    values: dict[str, object] = {
        "technologies": ["Python", "C#", "Java", "React"],
        "seniorities": ["junior", "mid"],
        "workModes": ["remote", "hybrid", "onsite"],
        "excludedTerms": [],
        "updatedAt": datetime.now(UTC),
    }
    values.update(changes)
    return SearchProfile.model_validate(values)


def test_normalization_and_technology_aliases() -> None:
    assert normalize_text("Júnior") == "junior"
    match = evaluate("Vaga remota para C#/.NET e React.js — nível Pleno", profile())
    assert match is not None
    assert match.technologies == ["C#", "React"]
    assert match.seniority == "mid"
    assert match.work_mode == "remote"


def test_java_does_not_match_javascript() -> None:
    assert evaluate("Pessoa desenvolvedora JavaScript júnior remoto", profile()) is None
    match = evaluate("Pessoa desenvolvedora Java e Spring júnior remoto", profile())
    assert match is not None
    assert match.technologies == ["Java"]


def test_unknown_seniority_is_included_and_senior_is_rejected() -> None:
    assert evaluate("Desenvolvimento Python remoto", profile()) is not None
    assert evaluate("Senior Python Engineer remoto", profile()) is None
    assert detect_seniority(normalize_text("Especialista React")) == "senior"


def test_work_mode_and_excluded_terms_are_respected() -> None:
    remote_only = profile(workModes=["remote"])
    assert evaluate("Python júnior presencial", remote_only, location="São Paulo, SP") is None
    assert evaluate("Python júnior", remote_only) is None
    excluded = profile(excludedTerms=["voluntário"])
    assert evaluate("Projeto voluntário Python júnior remoto", excluded) is None


def test_hybrid_and_onsite_jobs_are_limited_to_allowed_nearby_cities() -> None:
    assert evaluate(
        "Python pleno híbrido", profile(), location="São Paulo, SP"
    ) is not None
    assert evaluate(
        "Python pleno presencial", profile(), location="Campinas, SP"
    ) is not None
    assert evaluate("Python pleno híbrido", profile(), location="Jundiaí - SP") is not None
    assert evaluate(
        "Python pleno híbrido", profile(), location="Jundiaí, São Paulo, Brazil"
    ) is not None
    assert evaluate(
        "Python pleno presencial", profile(), location="Campinas e Região, SP"
    ) is not None
    assert evaluate("Python pleno presencial", profile(), location="ABC Paulista") is not None
    assert evaluate("Python pleno híbrido", profile(), location="Ribeirão Preto, SP") is None
    assert evaluate("Python pleno remoto", profile(), location="Recife, PE") is not None
