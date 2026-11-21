from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kali_api_url: str
    kali_job_finder_token: SecretStr
    github_token: SecretStr
    log_level: str = "INFO"
    request_timeout_seconds: float = Field(default=30, ge=5, le=120)
    backend_timeout_seconds: float = Field(default=90, ge=15, le=180)
    gupy_max_pages_per_term: int = Field(default=5, ge=1, le=20)
    linkedin_request_delay_seconds: float = Field(default=3, ge=0, le=30)

    @property
    def api_url(self) -> str:
        return self.kali_api_url.rstrip("/")
