"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings loaded from .env file or environment variables."""

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # LangSmith Observability
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "agentforge-healthcare"

    # OpenEMR FHIR API
    openemr_base_url: str = "https://localhost:9300"
    openemr_fhir_url: str = "https://localhost:9300/apis/default/fhir"
    openemr_token_url: str = "https://localhost:9300/oauth2/default/token"
    openemr_client_id: str = ""
    openemr_client_secret: str = ""
    openemr_username: str = ""
    openemr_password: str = ""
    fhir_verify_ssl: bool = True

    # Database
    database_path: str = "data/chat_history.db"

    # Agent settings
    default_llm: str = "claude"  # "claude" or "openai"
    max_tool_retries: int = 2
    response_timeout: int = 30

    # Security
    api_keys: str = ""  # comma-separated valid API keys; empty = no auth
    allowed_origins: str = "http://localhost:8501"
    environment: str = "development"  # "production" disables /docs

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
