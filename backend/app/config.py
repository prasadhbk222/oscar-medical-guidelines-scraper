from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://oscar:oscar@localhost:5432/oscar"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    source_page_url: str = "https://www.hioscar.com/clinical-guidelines/medical"
    pdf_dir: Path = ROOT_DIR / "data" / "pdfs"
    text_dir: Path = ROOT_DIR / "data" / "text"


settings = Settings()
