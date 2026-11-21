import re
import unicodedata
from dataclasses import dataclass

from job_finder.models import SearchProfile

TECHNOLOGY_PATTERNS: dict[str, tuple[str, ...]] = {
    "python": (r"\bpython\b",),
    "c#": (r"(?<!\w)c#(?!\w)", r"(?<!\w)\.net(?!\w)", r"\bdotnet\b", r"\basp\.net\b"),
    "java": (r"(?<!\w)java(?!script|\w)", r"\bspring(?: boot)?\b"),
    "react": (r"\breact(?:\.js|js)?\b", r"\bnext\.js\b"),
}

SENIOR_PATTERNS = (r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\blead\b", r"\bespecialista\b")
MID_PATTERNS = (r"\bpleno\b", r"\bmid(?:-level)?\b")
JUNIOR_PATTERNS = (r"\bjunior\b", r"\bjr\.?\b", r"\bentry(?:-level)?\b")

ALLOWED_LOCAL_CITIES = frozenset(
    {
        "barueri",
        "campinas",
        "carapicuiba",
        "cotia",
        "diadema",
        "guarulhos",
        "indaiatuba",
        "itupeva",
        "jundiai",
        "louveira",
        "maua",
        "mogi das cruzes",
        "osasco",
        "santana de parnaiba",
        "santo andre",
        "sao bernardo do campo",
        "sao caetano do sul",
        "sao paulo",
        "sorocaba",
        "taboao da serra",
        "valinhos",
        "vinhedo",
    }
)
ALLOWED_LOCAL_REGIONS = frozenset(
    {
        "abc paulista",
        "alphaville",
        "campinas metropolitan area",
        "grande sao paulo",
        "greater sao paulo area",
        "regiao metropolitana de campinas",
        "regiao metropolitana de sao paulo",
    }
)


@dataclass(frozen=True)
class Match:
    technologies: list[str]
    matched_terms: list[str]
    seniority: str
    work_mode: str


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_seniority(text: str) -> str:
    if _matches(text, SENIOR_PATTERNS):
        return "senior"
    if _matches(text, MID_PATTERNS):
        return "mid"
    if _matches(text, JUNIOR_PATTERNS):
        return "junior"
    return "unknown"


def detect_work_mode(text: str) -> str:
    if re.search(r"\b(remot[oa]|home office|100% remoto)\b", text):
        return "remote"
    if re.search(r"\b(hibrid[oa])\b", text):
        return "hybrid"
    if re.search(r"\b(presencial|on-site|onsite)\b", text):
        return "onsite"
    return "unknown"


def technology_matches(text: str, requested: list[str]) -> tuple[list[str], list[str]]:
    technologies: list[str] = []
    terms: list[str] = []
    for requested_name in requested:
        normalized_name = normalize_text(requested_name)
        patterns = TECHNOLOGY_PATTERNS.get(normalized_name)
        if patterns is None:
            escaped = re.escape(normalized_name)
            patterns = (rf"(?<!\w){escaped}(?!\w)",)
        if _matches(text, patterns):
            technologies.append(requested_name)
            terms.append(requested_name)
    return technologies, terms


def _is_allowed_local_location(location: str | None) -> bool:
    if not location:
        return False
    normalized = normalize_text(location).strip()
    if normalized in ALLOWED_LOCAL_REGIONS:
        return True
    suffix = (
        r"(?: e regiao)?"
        r"(?:\s*[-/]\s*sp|,\s*(?:sp|sao paulo))?"
        r"(?:,\s*(?:brasil|brazil))?"
    )
    return any(
        re.fullmatch(rf"{re.escape(city)}{suffix}", normalized)
        for city in ALLOWED_LOCAL_CITIES
    )


def evaluate(
    text: str, profile: SearchProfile, *, location: str | None = None
) -> Match | None:
    normalized = normalize_text(text)
    if any(normalize_text(term) in normalized for term in profile.excluded_terms):
        return None

    technologies, terms = technology_matches(normalized, profile.technologies)
    if not technologies:
        return None

    seniority = detect_seniority(normalized)
    if seniority == "senior" or (
        seniority != "unknown" and seniority not in profile.seniorities
    ):
        return None

    work_mode = detect_work_mode(normalized)
    all_modes = {"remote", "hybrid", "onsite"}
    selected_modes = set(profile.work_modes)
    if work_mode == "unknown" and selected_modes != all_modes:
        return None
    if work_mode != "unknown" and work_mode not in selected_modes:
        return None
    if work_mode in {"hybrid", "onsite"} and not _is_allowed_local_location(location):
        return None

    return Match(
        technologies=technologies,
        matched_terms=terms,
        seniority=seniority,
        work_mode=work_mode,
    )


def extract_location(title: str) -> str | None:
    match = re.match(r"\s*\[([^]]+)]", title)
    return match.group(1).strip() if match else None


def extract_company(title: str) -> str | None:
    match = re.search(r"\s(?:na|no|@)\s+([^|\[\]—–]+)$", title, flags=re.IGNORECASE)
    return match.group(1).strip(" -") if match else None
