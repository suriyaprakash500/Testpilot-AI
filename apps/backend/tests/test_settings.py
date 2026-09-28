"""Tests for centralized configuration (`app.core.config.Settings`).

Environment variables must override the built-in defaults. ``_env_file=None``
is used so the tests never depend on a developer's local ``.env`` file.
"""
from app.core.config import Settings


def test_defaults_when_no_env(monkeypatch):
    for key in (
        "LLM_PROVIDER",
        "AWS_REGION",
        "BEDROCK_MODEL_ID",
        "BEDROCK_GUARDRAIL_ID",
        "BEDROCK_GUARDRAIL_VERSION",
        "DATABASE_PATH",
        "ARTIFACTS_DIR",
        "REPOS_DIR",
        "BACKEND_PORT",
        "LLM_TEMPERATURE",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    s = Settings(_env_file=None)
    assert s.llm_provider == "openrouter"
    assert s.llm_temperature == 0.2
    assert s.aws_region == ""
    assert s.bedrock_model_id == ""
    assert s.database_path == "testpilot.db"
    assert s.backend_port == 3001
    assert s.log_level == "INFO"


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet")
    monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "gr-123")
    monkeypatch.setenv("BEDROCK_GUARDRAIL_VERSION", "1")
    monkeypatch.setenv("DATABASE_PATH", "/data/testpilot.db")
    monkeypatch.setenv("ARTIFACTS_DIR", "/artifacts")
    monkeypatch.setenv("REPOS_DIR", "/repos")
    monkeypatch.setenv("BACKEND_PORT", "8080")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")

    s = Settings(_env_file=None)
    assert s.llm_provider == "bedrock"
    assert s.aws_region == "us-east-1"
    assert s.bedrock_model_id == "anthropic.claude-3-5-sonnet"
    assert s.bedrock_guardrail_id == "gr-123"
    assert s.bedrock_guardrail_version == "1"
    assert s.database_path == "/data/testpilot.db"
    assert s.artifacts_dir == "/artifacts"
    assert s.repos_dir == "/repos"
    assert s.backend_port == 8080
    assert s.llm_temperature == 0.7


def test_env_vars_are_case_insensitive(monkeypatch):
    monkeypatch.setenv("llm_provider", "groq")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-70b")
    s = Settings(_env_file=None)
    assert s.llm_provider == "groq"
    assert s.groq_model == "llama-3.1-70b"


def test_extra_env_vars_are_ignored(monkeypatch):
    # Unknown variables must not raise (extra="ignore").
    monkeypatch.setenv("SOME_UNRELATED_VARIABLE", "whatever")
    s = Settings(_env_file=None)
    assert s is not None


def test_backward_compat_settings_attributes_exist():
    s = Settings(_env_file=None)
    # Attribute names relied upon elsewhere in the app must remain available.
    for attr in (
        "app_name",
        "environment",
        "backend_port",
        "backend_url",
        "frontend_url",
        "jwt_secret",
        "llm_provider",
        "llm_model",
        "openrouter_api_key",
        "groq_api_key",
        "groq_model",
        "github_client_id",
        "github_client_secret",
        "artifacts_dir",
        "repos_dir",
    ):
        assert hasattr(s, attr), f"missing settings attribute: {attr}"
