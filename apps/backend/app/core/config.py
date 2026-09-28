"""Centralized application configuration (Pydantic Settings).

All runtime configuration is grouped by domain:

* Application  — environment, ports, URLs, JWT secret, log level
* LLM          — provider selection and shared generation parameters
* AWS / Bedrock— region, model id and optional guardrail configuration
* OpenRouter   — existing values (behavior preserved)
* Groq         — existing values (behavior preserved)
* Storage      — configurable filesystem paths (no hard-coded deployment paths)

Environment variables are matched case-insensitively (e.g. ``LLM_PROVIDER`` or
``llm_provider`` both work). Existing ``.env`` discovery is preserved.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "Verity Backend"
    environment: str = "development"
    backend_port: int = 3001
    backend_url: str = "http://localhost:3001"
    frontend_url: str = "http://localhost:3000"
    jwt_secret: str = Field(default="super-secret-jwt-key-min-32-characters")
    log_level: str = Field(default="INFO")

    # --- LLM ---
    # Supported providers: "bedrock" | "openrouter" | "groq"
    llm_provider: str = Field(default="openrouter")
    llm_temperature: float = Field(default=0.2)
    # 0 means "unset" -> defer to the underlying library default.
    llm_max_tokens: int = Field(default=0)
    llm_timeout_s: float = Field(default=0.0)
    llm_max_retries: int = Field(default=2)

    # --- OpenRouter (existing behavior) ---
    llm_model: str = Field(default="stealth/ox-alpha")
    openrouter_api_key: str = Field(default="")

    # --- Groq (existing behavior) ---
    groq_api_key: str = Field(default="dummy-groq-key")
    groq_model: str = Field(default="openai/gpt-oss-120b")

    # --- AWS / Bedrock ---
    # No credentials live here — boto3's default provider chain (e.g. the EC2
    # IAM instance role) supplies them.
    aws_region: str = Field(default="")
    bedrock_model_id: str = Field(default="")
    bedrock_guardrail_id: str = Field(default="")
    bedrock_guardrail_version: str = Field(default="")

    # --- GitHub (existing behavior) ---
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")

    # --- Storage (all configurable) ---
    database_path: str = Field(default="testpilot.db")
    artifacts_dir: str = Field(default="./artifacts")
    repos_dir: str = Field(default="./repos")

    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env", "../.env"],
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
