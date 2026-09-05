import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_current_dir)
_root_dir = os.path.dirname(_backend_dir)

_env_file_paths = [
    os.path.join(_root_dir, ".env"),
    os.path.join(_backend_dir, ".env"),
    ".env"
]

class Settings(BaseSettings):
    # DB Configuration
    DATABASE_URL: str = "sqlite:///./retry.db"

    # AI Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "llama3.1:8b"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_WORKSPACE_ID: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Razorpay Keys (Test mode by default)
    RAZORPAY_KEY_ID: str = "rzp_test_dummy_id"
    RAZORPAY_KEY_SECRET: str = "rzp_test_dummy_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "dummy_webhook_secret"

    # Sandbox Credentials (Email / SMS)
    RESEND_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Guardrails config
    MAX_RETRY_ATTEMPTS: int = 4
    MAX_DAILY_CONTACTS: int = 3

    model_config = SettingsConfigDict(
        env_file=_env_file_paths,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

