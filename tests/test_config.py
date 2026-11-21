from job_finder.config import Settings


def make_settings(gupy_urls: str) -> Settings:
    return Settings(
        kali_api_url="https://api.example.com",
        kali_job_finder_token="token",
        github_token="token",
        gupy_urls=gupy_urls,
    )


def test_manual_gupy_urls_accepts_concatenated_workflow_input() -> None:
    first = "https://first.gupy.io/job/one?jobBoardSource=gupy_portal"
    second = "https://second.gupy.io/job/two?jobBoardSource=gupy_portal"

    assert make_settings(first + second).manual_gupy_urls == [first, second]


def test_manual_gupy_urls_deduplicates_whitespace_separated_input() -> None:
    first = "https://first.gupy.io/job/one"
    second = "https://second.gupy.io/job/two"

    assert make_settings(f"{first}\n{second} {first}").manual_gupy_urls == [first, second]
