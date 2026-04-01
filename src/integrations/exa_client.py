"""Direct Exa API client for LangGraph agent integration.

This module provides a clean, async-compatible wrapper around the Exa API
without dependencies on MCP servers or additional frameworks.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

from ..config import ExaSettings, get_exa_config


class ExaSearchResult(BaseModel):
    """Single search result from Exa API."""

    title: str
    url: str
    published_date: datetime | None = None
    author: str | None = None
    score: float | None = None
    id: str
    image: str | None = None
    favicon: str | None = None
    text: str | None = None
    highlights: list[str] | None = None
    highlight_scores: list[float] | None = None
    summary: str | None = None


class ExaSearchResponse(BaseModel):
    """Response from Exa search API."""

    request_id: str
    resolved_search_type: str
    results: list[ExaSearchResult]
    search_type: str
    context: str | None = None
    cost_dollars: dict[str, Any] | None = None


class ExaResearchTask(BaseModel):
    """Research task for Exa Research API."""

    id: str
    status: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class ExaClient:
    """Direct Exa API client optimized for LangGraph agent integration.

    Features:
    - Full async/await support
    - Comprehensive error handling with retries
    - Agent-friendly response models
    - Cost tracking and optimization
    - Authentication management
    """

    def __init__(
        self,
        config: ExaSettings | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        """Initialize Exa client with centralized configuration.

        Args:
            config: ExaSettings instance. If None, uses global settings.
            api_key: Exa API key override. If None, uses config or environment variable.
            base_url: Base URL override. If None, uses config default.
            timeout: Request timeout override. If None, uses config default.
            max_retries: Max retries override. If None, uses config default.

        """
        # Use provided config or get from global settings
        if config is None:
            config_dict = get_exa_config()
            self.config = ExaSettings(**config_dict)
        else:
            self.config = config

        # Apply overrides if provided
        self.api_key = api_key or self.config.api_key
        if not self.api_key:
            raise ValueError(
                "EXA_API_KEY must be provided via config, parameter, "
                "or environment variable"
            )

        self.base_url = base_url or str(self.config.base_url)
        self.timeout = timeout or self.config.timeout_seconds
        self.max_retries = max_retries or self.config.max_retries
        self.base_retry_delay = self.config.base_retry_delay

        # Store config defaults for method usage
        self.default_search_type = self.config.search_type
        self.default_num_results = self.config.num_results
        self.default_include_text = self.config.include_text
        self.default_include_highlights = self.config.include_highlights
        self.default_include_summary = self.config.include_summary

        # Initialize async HTTP client
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic and error handling."""
        client = await self._get_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < self.max_retries:
                    wait_time = self.base_retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)
                    continue

                error_detail = "Unknown error"
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("error", {}).get("message", str(e))
                except Exception:
                    error_detail = str(e)

                raise Exception(f"Exa API error: {error_detail}") from e

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    wait_time = self.base_retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception("Exa API request timed out") from None

            except Exception as e:
                if attempt < self.max_retries:
                    wait_time = self.base_retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception(f"Exa API request failed: {e!s}") from e

        raise Exception("Maximum retry attempts exceeded")

    async def search(
        self,
        query: str,
        search_type: str | None = None,
        num_results: int | None = None,
        include_text: bool | None = None,
        include_highlights: bool | None = None,
        include_summary: bool | None = None,
        category: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        start_crawl_date: str | None = None,
        end_crawl_date: str | None = None,
        start_published_date: str | None = None,
        end_published_date: str | None = None,
    ) -> ExaSearchResponse:
        """Search the web using Exa's neural or keyword search.

        Args:
            query: Search query string.
            search_type: Type of search ("auto", "neural", "keyword", "fast").
            num_results: Number of results to return (max 100).
            include_text: Whether to include full page text.
            include_highlights: Whether to include highlighted snippets.
            include_summary: Whether to include page summaries.
            category: Focus category ("company", "research paper", "news", etc.).
            include_domains: Only search these domains.
            exclude_domains: Exclude these domains.
            start_crawl_date: Filter by crawl date (ISO format).
            end_crawl_date: Filter by crawl date (ISO format).
            start_published_date: Filter by publish date (ISO format).
            end_published_date: Filter by publish date (ISO format).

        Returns:
            ExaSearchResponse with search results.

        """
        # Apply configuration defaults
        search_type = search_type or self.default_search_type
        num_results = num_results or self.default_num_results
        include_text = (
            include_text if include_text is not None else self.default_include_text
        )
        include_highlights = (
            include_highlights
            if include_highlights is not None
            else self.default_include_highlights
        )
        include_summary = (
            include_summary
            if include_summary is not None
            else self.default_include_summary
        )

        # Build request payload
        payload = {
            "query": query,
            "type": search_type,
            "numResults": min(num_results, 100),
        }

        # Add optional parameters
        if category:
            payload["category"] = category
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        if start_crawl_date:
            payload["startCrawlDate"] = start_crawl_date
        if end_crawl_date:
            payload["endCrawlDate"] = end_crawl_date
        if start_published_date:
            payload["startPublishedDate"] = start_published_date
        if end_published_date:
            payload["endPublishedDate"] = end_published_date

        # Configure content extraction
        if include_text or include_highlights or include_summary:
            contents = {}
            if include_text:
                contents["text"] = True
            if include_highlights:
                contents["highlights"] = {}
            if include_summary:
                contents["summary"] = {}
            payload["contents"] = contents

        # Make API request
        response_data = await self._make_request("POST", "/search", data=payload)

        # Parse results
        results = []
        for result_data in response_data.get("results", []):
            result = ExaSearchResult(
                title=result_data.get("title", ""),
                url=result_data.get("url", ""),
                published_date=result_data.get("publishedDate"),
                author=result_data.get("author"),
                score=result_data.get("score"),
                id=result_data.get("id", ""),
                image=result_data.get("image"),
                favicon=result_data.get("favicon"),
                text=result_data.get("text"),
                highlights=result_data.get("highlights"),
                highlight_scores=result_data.get("highlightScores"),
                summary=result_data.get("summary"),
            )
            results.append(result)

        return ExaSearchResponse(
            request_id=response_data.get("requestId", ""),
            resolved_search_type=response_data.get("resolvedSearchType", ""),
            results=results,
            search_type=response_data.get("searchType", ""),
            context=response_data.get("context"),
            cost_dollars=response_data.get("costDollars"),
        )

    async def search_and_contents(
        self,
        query: str,
        num_results: int = 5,
        include_text: bool = True,
        include_summary: bool = True,
    ) -> list[ExaSearchResult]:
        """Search and get contents in a single call.
        
        Args:
            query: Search query.
            num_results: Number of results.
            include_text: Whether to include text.
            include_summary: Whether to include summary.
            
        Returns:
            List of results with contents.
        """
        response = await self.search(
            query=query,
            num_results=num_results,
            include_text=include_text,
            include_summary=include_summary,
        )
        return response.results

    async def get_contents(
        self,
        ids: list[str],
        include_text: bool = True,
        include_highlights: bool = False,
        include_summary: bool = False,
    ) -> list[ExaSearchResult]:
        """Get full content for specific URLs by their IDs.

        Args:
            ids: List of document IDs from search results.
            include_text: Whether to include full page text.
            include_highlights: Whether to include highlighted snippets.
            include_summary: Whether to include page summaries.

        Returns:
            List of ExaSearchResult with content.

        """
        payload = {
            "ids": ids,
        }

        # Configure content extraction
        contents = {}
        if include_text:
            contents["text"] = True
        if include_highlights:
            contents["highlights"] = {}
        if include_summary:
            contents["summary"] = {}

        if contents:
            payload["contents"] = contents

        response_data = await self._make_request("POST", "/contents", data=payload)

        # Parse results
        results = []
        for result_data in response_data.get("results", []):
            result = ExaSearchResult(
                title=result_data.get("title", ""),
                url=result_data.get("url", ""),
                published_date=result_data.get("publishedDate"),
                author=result_data.get("author"),
                score=result_data.get("score"),
                id=result_data.get("id", ""),
                image=result_data.get("image"),
                favicon=result_data.get("favicon"),
                text=result_data.get("text"),
                highlights=result_data.get("highlights"),
                highlight_scores=result_data.get("highlightScores"),
                summary=result_data.get("summary"),
            )
            results.append(result)

        return results

    async def find_similar(
        self,
        url: str,
        num_results: int = 10,
        include_text: bool = False,
        include_highlights: bool = False,
        include_summary: bool = False,
    ) -> list[ExaSearchResult]:
        """Find pages similar to a given URL.

        Args:
            url: Reference URL to find similar pages.
            num_results: Number of similar results to return.
            include_text: Whether to include full page text.
            include_highlights: Whether to include highlighted snippets.
            include_summary: Whether to include page summaries.

        Returns:
            List of similar ExaSearchResult.

        """
        payload = {
            "url": url,
            "numResults": num_results,
        }

        # Configure content extraction
        if include_text or include_highlights or include_summary:
            contents = {}
            if include_text:
                contents["text"] = True
            if include_highlights:
                contents["highlights"] = {}
            if include_summary:
                contents["summary"] = {}
            payload["contents"] = contents

        response_data = await self._make_request("POST", "/findSimilar", data=payload)

        # Parse results
        results = []
        for result_data in response_data.get("results", []):
            result = ExaSearchResult(
                title=result_data.get("title", ""),
                url=result_data.get("url", ""),
                published_date=result_data.get("publishedDate"),
                author=result_data.get("author"),
                score=result_data.get("score"),
                id=result_data.get("id", ""),
                image=result_data.get("image"),
                favicon=result_data.get("favicon"),
                text=result_data.get("text"),
                highlights=result_data.get("highlights"),
                highlight_scores=result_data.get("highlightScores"),
                summary=result_data.get("summary"),
            )
            results.append(result)

        return results

    async def answer(
        self,
        query: str,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Get a direct answer to a question using Exa's Answer API.

        Args:
            query: Question to answer.
            include_domains: Only search these domains.
            exclude_domains: Exclude these domains.
            category: Focus category.

        Returns:
            Answer response with text and sources.

        """
        payload = {
            "query": query,
        }

        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        if category:
            payload["category"] = category

        return await self._make_request("POST", "/answer", data=payload)

    async def create_research_task(
        self,
        instructions: str,
        model: str = "exa-research",
        output_schema: dict[str, Any] | None = None,
        infer_schema: bool = False,
    ) -> ExaResearchTask:
        """Create a research task for automated web research.

        Args:
            instructions: Detailed instructions for the research task.
            model: Research model ("exa-research" or "exa-research-pro").
            output_schema: JSON schema for structured output.
            infer_schema: Whether to automatically infer output schema.

        Returns:
            ExaResearchTask with task ID.

        """
        payload = {
            "instructions": instructions,
            "model": model,
        }

        if output_schema or infer_schema:
            output_config = {}
            if output_schema:
                output_config["schema"] = output_schema
            if infer_schema:
                output_config["inferSchema"] = infer_schema
            payload["output"] = output_config

        response_data = await self._make_request(
            "POST", "/research/v0/tasks", data=payload
        )

        return ExaResearchTask(
            id=response_data["id"],
            status="pending",
        )

    async def get_research_task(self, task_id: str) -> ExaResearchTask:
        """Get the status and results of a research task.

        Args:
            task_id: Research task ID.

        Returns:
            ExaResearchTask with current status and results.

        """
        response_data = await self._make_request("GET", f"/research/v0/tasks/{task_id}")

        return ExaResearchTask(
            id=task_id,
            status=response_data.get("status"),
            result=response_data.get("result"),
            error=response_data.get("error"),
        )

    async def wait_for_research_task(
        self,
        task_id: str,
        max_wait_time: int = 300,
        poll_interval: int = 5,
    ) -> ExaResearchTask:
        """Wait for a research task to complete.

        Args:
            task_id: Research task ID.
            max_wait_time: Maximum time to wait in seconds.
            poll_interval: Time between status checks in seconds.

        Returns:
            Completed ExaResearchTask.

        """
        start_time = asyncio.get_event_loop().time()

        while True:
            task = await self.get_research_task(task_id)

            if task.status in ["completed", "failed"]:
                return task

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= max_wait_time:
                raise Exception(
                    f"Research task {task_id} timed out after {max_wait_time} seconds"
                )

            await asyncio.sleep(poll_interval)

    async def research(
        self,
        instructions: str,
        model: str = "exa-research",
        output_schema: dict[str, Any] | None = None,
        infer_schema: bool = False,
        wait_for_completion: bool = True,
        max_wait_time: int = 300,
    ) -> ExaResearchTask | dict[str, Any]:
        """Create and optionally wait for research task completion.

        Args:
            instructions: Research instructions.
            model: Research model.
            output_schema: JSON schema for output.
            infer_schema: Whether to infer schema.
            wait_for_completion: Whether to wait for task completion.
            max_wait_time: Maximum wait time in seconds.

        Returns:
            Research task or completed results.

        """
        task = await self.create_research_task(
            instructions=instructions,
            model=model,
            output_schema=output_schema,
            infer_schema=infer_schema,
        )

        if wait_for_completion:
            completed_task = await self.wait_for_research_task(
                task.id,
                max_wait_time=max_wait_time,
            )
            return completed_task.result if completed_task.result else completed_task

        return task

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
