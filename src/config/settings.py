import os
from pathlib import Path

from dotenv import load_dotenv

# Load <project root>/.env explicitly so it works from any working directory.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o")
    temperature: float = float(os.getenv("TEMPERATURE", "0.3"))
    
    
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///:memory:")

    port: int = int(os.getenv("PORT", os.getenv("APP_PORT", "7860")))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    # Write full tool responses to the log. They can hold customer data (addresses, emails),
    # so turn this off outside local development.
    log_tool_payloads: bool = os.getenv("LOG_TOOL_PAYLOADS", "true").lower() in ("1", "true", "yes")


settings = Settings()
