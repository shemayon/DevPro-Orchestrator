"""Unified Configuration Settings Management for AI Job Scraper Orchestration.

This module provides centralized, hierarchical configuration management using
pydantic-settings v2.10.1+ with comprehensive validation, multiple source support,
and DRY principle enforcement across the orchestration layer.

Features:
- Hierarchical BaseSettings classes with nested models
- Environment variable support with ORCHESTRATION_ prefix
- Comprehensive field validation and custom validators
- Type safety with runtime validation
- Support for .env files, CLI overrides, and secrets files
- Performance optimized with global settings caching
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIClientSettings(BaseSettings):
    """Shared API client configuration with common patterns.

    Base class for all API client configurations providing standardized
    timeout, retry, and authentication patterns.
    """

    timeout_seconds: int = Field(
        60, ge=1, le=600, description="Request timeout in seconds"
    )
    max_retries: int = Field(
        3, ge=1, le=10, description="Maximum retry attempts for failed requests"
    )
    base_retry_delay: float = Field(
        1.0,
        ge=0.1,
        le=10.0,
        description="Base delay between retries (exponential backoff)",
    )


class OpenAISettings(APIClientSettings):
    """OpenAI/OpenAI-compatible API configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: str = Field(..., description="OpenAI API key")
    base_url: HttpUrl = Field(
        "https://api.openai.com/v1", description="OpenAI API base URL"
    )
    model: str = Field("gpt-4o-mini", description="Default OpenAI model name")
    temperature: float = Field(
        0.1, ge=0.0, le=2.0, description="Default temperature for model completions"
    )
    max_tokens: int = Field(
        4000, ge=1, le=200000, description="Maximum tokens for completions"
    )


class OpenRouterSettings(APIClientSettings):
    """OpenRouter API configuration for alternative model access."""

    model_config = SettingsConfigDict(env_prefix="OPENROUTER_")

    api_key: str = Field(..., description="OpenRouter API key")
    base_url: HttpUrl = Field(
        "https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )
    model: str = Field(
        "openrouter/horizon-beta", description="Default OpenRouter model name"
    )
    temperature: float = Field(
        0.2, ge=0.0, le=2.0, description="Default temperature for model completions"
    )
    max_tokens: int = Field(
        4000, ge=1, le=200000, description="Maximum tokens for completions"
    )
    # OpenRouter extended timeout for larger models
    timeout_seconds: int = Field(
        90, ge=1, le=600, description="Extended timeout for OpenRouter requests"
    )


class ExaSettings(APIClientSettings):
    """Exa API configuration for web search and research."""

    model_config = SettingsConfigDict(env_prefix="EXA_")

    api_key: str = Field(..., description="Exa API key")
    base_url: HttpUrl = Field("https://api.exa.ai", description="Exa API base URL")
    search_type: str = Field(
        "auto", description="Default search type (auto, neural, keyword, fast)"
    )
    num_results: int = Field(
        10, ge=1, le=100, description="Default number of search results"
    )
    include_text: bool = Field(False, description="Include full page text by default")
    include_highlights: bool = Field(
        True, description="Include highlighted snippets by default"
    )
    include_summary: bool = Field(
        False, description="Include page summaries by default"
    )


class Crawl4AISettings(APIClientSettings):
    """Crawl4AI configuration for local web scraping and crawling.

    Crawl4AI runs locally using Playwright, so it doesn't require an API key
    but can be configured for browser behavior and extraction strategies.
    """

    model_config = SettingsConfigDict(env_prefix="CRAWL4AI_")

    # Browser settings
    headless: bool = Field(True, description="Run browser in headless mode")
    use_proxy: bool = Field(False, description="Whether to use a proxy for crawling")
    proxy_url: str | None = Field(None, description="Proxy URL if use_proxy is True")

    # Content settings
    default_formats: list[str] = Field(
        ["markdown"], description="Default output formats for scraping"
    )
    only_main_content: bool = Field(
        True, description="Extract only main content by default"
    )

    # Crawling limits (for batch operations)
    crawl_limit: int = Field(
        100, ge=1, le=1000, description="Default limit for batch crawl operations"
    )


class DatabaseSettings(BaseSettings):
    """Database configuration for orchestration system."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = Field("sqlite:///jobs.db", description="Main database connection URL")
    implementation_tracker_path: Path = Field(
        Path("orchestration/database/implementation_tracker.db"),
        description="Task manager database file path",
    )
    pool_size: int = Field(10, ge=1, le=50, description="Database connection pool size")
    pool_timeout: int = Field(
        30, ge=1, le=300, description="Database connection timeout (seconds)"
    )
    echo_sql: bool = Field(False, description="Enable SQL query logging for debugging")

    @field_validator("implementation_tracker_path")
    @classmethod
    def validate_db_path(cls, v: Path) -> Path:
        """Ensure database directory exists and is writable."""
        # Convert to absolute path if relative
        if not v.is_absolute():
            v = Path.cwd() / v

        # Create parent directories if they don't exist
        v.parent.mkdir(parents=True, exist_ok=True)

        # Check if directory is writable
        if not os.access(v.parent, os.W_OK):
            raise ValueError(f"Database directory is not writable: {v.parent}")

        return v


class AgentSettings(BaseSettings):
    """Agent-specific configuration for different agent types."""

    # Temperature settings for different agent types
    research_temperature: float = Field(
        0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for research agents (precise analysis)",
    )
    coding_temperature: float = Field(
        0.2,
        ge=0.0,
        le=2.0,
        description="Temperature for coding agents (balanced creativity)",
    )
    testing_temperature: float = Field(
        0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for testing agents (precise validation)",
    )
    documentation_temperature: float = Field(
        0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for documentation agents (creative writing)",
    )

    # Execution limits
    max_execution_time_minutes: int = Field(
        30, ge=1, le=120, description="Maximum execution time per agent task (minutes)"
    )
    max_iterations: int = Field(
        5, ge=1, le=20, description="Maximum iterations for iterative tasks"
    )

    # Quality thresholds
    minimum_confidence_score: float = Field(
        0.7, ge=0.0, le=1.0, description="Minimum confidence score for task completion"
    )


class SupervisorSettings(BaseSettings):
    """LangGraph supervisor configuration."""

    model: str = Field(
        "openrouter/horizon-beta", description="Model for supervisor decision making"
    )
    temperature: float = Field(
        0.2, ge=0.0, le=2.0, description="Temperature for supervisor reasoning"
    )
    max_parallel_agents: int = Field(
        5, ge=1, le=20, description="Maximum number of agents running in parallel"
    )
    task_assignment_strategy: str = Field(
        "load_balanced", description="Strategy for assigning tasks to agents"
    )
    supervision_interval_seconds: int = Field(
        30, ge=5, le=300, description="Interval for supervisor status checks"
    )
    auto_retry_failed_tasks: bool = Field(
        True, description="Automatically retry failed tasks"
    )
    max_retry_attempts: int = Field(
        3, ge=1, le=10, description="Maximum retry attempts for failed tasks"
    )


class OrchestrationSettings(BaseSettings):
    """Main orchestration configuration combining all subsystem settings.

    This is the root configuration class that aggregates all other settings
    and provides the global configuration interface for the orchestration system.
    """

    # API Services
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    exa: ExaSettings = Field(default_factory=ExaSettings)
    crawl4ai: Crawl4AISettings = Field(default_factory=Crawl4AISettings)

    # Infrastructure
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    agents: AgentSettings = Field(default_factory=AgentSettings)
    supervisor: SupervisorSettings = Field(default_factory=SupervisorSettings)

    # Legacy feature flags (for backward compatibility)
    use_groq: bool = Field(
        False, description="Use Groq API instead of OpenAI (legacy flag)"
    )
    use_proxies: bool = Field(
        False, description="Enable proxy usage for scraping (legacy flag)"
    )
    use_checkpointing: bool = Field(True, description="Enable workflow checkpointing")

    # Performance and execution settings
    parallel_execution_limit: int = Field(
        5, ge=1, le=20, description="Maximum parallel agent executions"
    )
    batch_size: int = Field(
        10, ge=1, le=100, description="Default batch processing size"
    )
    task_timeout_minutes: int = Field(
        60, ge=1, le=480, description="Global task timeout in minutes"
    )

    # Development and debugging
    debug_mode: bool = Field(False, description="Enable debug logging and validation")
    log_level: str = Field(
        "INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Configuration metadata
    config_version: str = Field("1.0.0", description="Configuration schema version")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="ORCHESTRATION_",
        extra="ignore",
        validate_default=True,
        case_sensitive=False,
        # Support secrets file for production
        secrets_dir=os.getenv("ORCHESTRATION_SECRETS_DIR"),
        # Enable aliased environment variables
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> "OrchestrationSettings":
        """Perform cross-field validation and consistency checks."""
        # Ensure parallel limits are consistent
        if self.parallel_execution_limit > self.supervisor.max_parallel_agents:
            self.parallel_execution_limit = self.supervisor.max_parallel_agents

        # Validate timeout relationships
        if self.task_timeout_minutes < self.agents.max_execution_time_minutes:
            raise ValueError("Global task timeout must be >= agent max execution time")

        # Validate database path consistency
        if not self.database.implementation_tracker_path.exists():
            # Ensure parent directory exists
            self.database.implementation_tracker_path.parent.mkdir(
                parents=True, exist_ok=True
            )

        return self

    def get_agent_config(self, agent_type: str) -> dict[str, Any]:
        """Get configuration for a specific agent type.

        Args:
            agent_type: Type of agent (research, coding, testing, documentation)

        Returns:
            Dictionary of agent-specific configuration values

        Raises:
            ValueError: If agent type is unknown

        """
        base_config = {
            "max_execution_time_minutes": self.agents.max_execution_time_minutes,
            "max_iterations": self.agents.max_iterations,
            "minimum_confidence_score": self.agents.minimum_confidence_score,
            "timeout_seconds": self.openrouter.timeout_seconds,
            "max_retries": self.openrouter.max_retries,
        }

        # Add agent-specific temperature
        temperature_map = {
            "research": self.agents.research_temperature,
            "coding": self.agents.coding_temperature,
            "testing": self.agents.testing_temperature,
            "documentation": self.agents.documentation_temperature,
        }

        base_config["temperature"] = temperature_map.get(
            agent_type, self.agents.coding_temperature
        )

        return base_config

    def get_api_client_config(self, client_type: str) -> dict[str, Any]:
        """Get configuration for a specific API client.

        Args:
            client_type: Type of client (openai, openrouter, exa, firecrawl)

        Returns:
            Dictionary of client configuration values

        Raises:
            ValueError: If client type is unknown

        """
        client_map = {
            "openai": self.openai,
            "openrouter": self.openrouter,
            "exa": self.exa,
            "crawl4ai": self.crawl4ai,
        }

        client_config = client_map.get(client_type)
        if not client_config:
            raise ValueError(f"Unknown client type: {client_type}")

        return client_config.model_dump()


# Global settings instance with caching
@lru_cache(maxsize=1)
def get_settings() -> OrchestrationSettings:
    """Get cached global settings instance.

    Uses LRU cache to ensure settings are loaded only once and reused
    across the application for optimal performance.

    Returns:
        Global OrchestrationSettings instance

    """
    return OrchestrationSettings()


# Global settings instance for easy import
settings = get_settings()


# Convenience functions for common configuration access patterns
def get_database_url() -> str:
    """Get the main database URL."""
    return settings.database.url


def get_task_database_path() -> Path:
    """Get the task manager database path."""
    return settings.database.implementation_tracker_path


def get_openrouter_config() -> dict[str, Any]:
    """Get OpenRouter client configuration."""
    return settings.get_api_client_config("openrouter")


def get_exa_config() -> dict[str, Any]:
    """Get Exa client configuration."""
    return settings.get_api_client_config("exa")


def get_crawl4ai_config() -> dict[str, Any]:
    """Get Crawl4AI client configuration."""
    return settings.get_api_client_config("crawl4ai")


def validate_configuration() -> bool:
    """Validate current configuration and raise descriptive errors if invalid.

    Returns:
        True if configuration is valid

    Raises:
        ValueError: If configuration is invalid with detailed error message

    """
    try:
        # Attempt to instantiate settings (triggers all validation)
        test_settings = OrchestrationSettings()

        # Additional runtime validation
        required_api_keys = [
            ("OpenRouter", test_settings.openrouter.api_key),
            ("Exa", test_settings.exa.api_key),
        ]

        missing_keys = [
            service
            for service, key in required_api_keys
            if not key or key.strip() == ""
        ]

        if missing_keys:
            raise ValueError(
                f"Missing required API keys: {', '.join(missing_keys)}. "
                f"Please set the corresponding environment variables."
            )

        # Validate database accessibility
        db_path = test_settings.database.implementation_tracker_path
        if not os.access(db_path.parent, os.W_OK):
            raise ValueError(f"Database directory is not writable: {db_path.parent}")

        return True

    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e!s}") from e


# Export commonly used settings for convenience
__all__ = [
    "APIClientSettings",
    "AgentSettings",
    "DatabaseSettings",
    "ExaSettings",
    "Crawl4AISettings",
    "OpenAISettings",
    "OpenRouterSettings",
    "OrchestrationSettings",
    "SupervisorSettings",
    "get_database_url",
    "get_exa_config",
    "get_crawl4ai_config",
    "get_openrouter_config",
    "get_settings",
    "get_task_database_path",
    "settings",
    "validate_configuration",
]
