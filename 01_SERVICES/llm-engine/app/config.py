from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tier: Literal["server", "local"] = Field(default="server", alias="UDITO_TIER")

    llm_base_url: str = Field(default="http://ollama:11434/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="ollama", alias="LLM_API_KEY")
    llm_model: str = Field(default="qwen2.5:3b-instruct", alias="LLM_MODEL")
    llm_warmup_on_start: bool = Field(default=True, alias="LLM_WARMUP_ON_START")
    llm_max_tokens_default: int = Field(default=80, alias="LLM_MAX_TOKENS_DEFAULT")

    redis_url: str = Field(default="", alias="REDIS_URL")
    memory_window_size: int = Field(default=8, alias="MEMORY_WINDOW_SIZE")
    memory_ttl_seconds: int = Field(default=86400, alias="MEMORY_TTL_SECONDS")

    api_port: int = Field(default=8080, alias="API_PORT")
    cors_allow_origins: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def use_redis(self) -> bool:
        return bool(self.redis_url.strip())


settings = Settings()
