from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # SerpAPI
    serpapi_key: str = Field(default="", alias="SERPAPI_KEY")

    # Gmail OAuth
    gmail_client_id: str = Field(default="", alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(default="", alias="GMAIL_CLIENT_SECRET")

    # LinkedIn
    linkedin_email: str = Field(default="", alias="LINKEDIN_EMAIL")
    linkedin_password: str = Field(default="", alias="LINKEDIN_PASSWORD")

    # Job search preferences
    target_roles: List[str] = Field(default=["Software Engineer", "Backend Engineer", "Full Stack Engineer"])
    target_locations: List[str] = Field(default=["Remote", "San Francisco", "New York"])
    min_fit_score: int = Field(default=6, alias="MIN_FIT_SCORE")
    target_comp_min: int = Field(default=150000, alias="TARGET_COMP_MIN")

    # Database
    db_path: str = "data/jobs.db"

    # Claude model
    claude_model: str = "claude-sonnet-4-6"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @classmethod
    def _parse_list_env(cls, v: str) -> List[str]:
        return [item.strip() for item in v.split(",") if item.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow comma-separated strings for list fields
        env_parse_none_str="None",
    )


settings = Settings()
