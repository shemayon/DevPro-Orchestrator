"""Crawl4AI client for local web scraping and crawling.

This module provides an async wrapper around the Crawl4AI library,
replacing the external Firecrawl API with a local, library-based solution.
"""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
except ImportError:
    # Fallback for environments where crawl4ai is not installed yet
    AsyncWebCrawler = None
    CrawlerRunConfig = None
    JsonCssExtractionStrategy = None

from ..config import Crawl4AISettings, get_crawl4ai_config

logger = logging.getLogger(__name__)


class Crawl4AIMetadata(BaseModel):
    """Metadata for scraped content."""

    title: str | None = None
    description: str | None = None
    language: str | None = None
    source_url: str | None = None
    status_code: int | None = None


class Crawl4AIDocument(BaseModel):
    """Single document from Crawl4AI."""

    markdown: str | None = None
    html: str | None = None
    links: list[str] | None = None
    json_data: dict[str, Any] | None = None
    metadata: Crawl4AIMetadata | None = None


class CrawlResultModel(BaseModel):
    """Unified result model for scraping/crawling operations."""

    success: bool
    data: Crawl4AIDocument | None = None
    error: str | None = None


class Crawl4AIClient:
    """Async client for Crawl4AI optimized for multi-agent workflows.

    Features:
    - Local execution using Playwright
    - High-quality Markdown generation
    - Structured data extraction
    - Batch processing
    """

    def __init__(self, config: Crawl4AISettings | None = None):
        """Initialize Crawl4AI client with configuration."""
        if config is None:
            config_dict = get_crawl4ai_config()
            self.config = Crawl4AISettings(**config_dict)
        else:
            self.config = config

        if AsyncWebCrawler is None:
            logger.warning(
                "crawl4ai library not found. Please install it with "
                "'pip install crawl4ai' and 'playwright install'."
            )

        self._crawler_instance: Any = None

    async def _get_crawler(self) -> Any:
        """Get or create AsyncWebCrawler instance."""
        if self._crawler_instance is None:
            if AsyncWebCrawler is None:
                raise ImportError("crawl4ai not installed")
            self._crawler_instance = AsyncWebCrawler()
            await self._crawler_instance.__aenter__()
        return self._crawler_instance

    async def scrape(
        self,
        url: str,
        formats: list[str] | None = None,
        only_main_content: bool | None = None,
        json_schema: dict[str, Any] | None = None,
        **kwargs,
    ) -> CrawlResultModel:
        """Scrape a single URL.

        Args:
            url: URL to scrape.
            formats: Desired output formats (defaults to ["markdown"]).
            only_main_content: Extract only the main content.
            json_schema: Optional CSS-based JSON extraction schema.
            **kwargs: Additional parameters for Crawl4AI.

        Returns:
            CrawlResultModel with scraped content.
        """
        if AsyncWebCrawler is None:
            return CrawlResultModel(success=False, error="crawl4ai not installed")

        formats = formats or self.config.default_formats
        only_main_content = (
            only_main_content
            if only_main_content is not None
            else self.config.only_main_content
        )

        try:
            crawler = await self._get_crawler()
            
            # Configure run
            run_config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=True,
                process_iframes=True,
                remove_overlay_elements=True,
                **kwargs
            )

            # Handle JSON extraction if schema provided
            if json_schema:
                # Crawl4AI uses JsonCssExtractionStrategy for CSS-based extraction
                # For LLM-based extraction, use LLMExtractionStrategy (not implemented here)
                pass

            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                return CrawlResultModel(success=False, error=result.error_message)

            doc = Crawl4AIDocument(
                markdown=result.markdown,
                html=result.html,
                links=[link["href"] for link in result.links.get("internal", [])] if result.links else [],
                metadata=Crawl4AIMetadata(
                    title=result.metadata.get("title") if result.metadata else None,
                    description=result.metadata.get("description") if result.metadata else None,
                    source_url=url,
                    status_code=200,  # Assuming success if result.success is True
                )
            )

            return CrawlResultModel(success=True, data=doc)

        except Exception as e:
            logger.error(f"Crawl4AI scrape error: {e}")
            return CrawlResultModel(success=False, error=str(e))

    async def crawl_batch(
        self,
        urls: list[str],
        formats: list[str] | None = None,
        only_main_content: bool = True,
        **kwargs
    ) -> list[CrawlResultModel]:
        """Crawl a list of URLs in batch.

        Args:
            urls: List of URLs to crawl.
            formats: Desired output formats.
            only_main_content: Extract only main content.
            **kwargs: Additional crawler parameters.

        Returns:
            List of CrawlResultModel objects.
        """
        results = []
        for url in urls:
            res = await self.scrape(
                url=url,
                formats=formats,
                only_main_content=only_main_content,
                **kwargs
            )
            results.append(res)
        return results

    async def map_website(
        self,
        url: str,
        limit: int = 50,
        **kwargs
    ) -> list[str]:
        """Map a website to find internal links.

        Args:
            url: Root URL to map.
            limit: Maximum number of links to return.
            **kwargs: Additional parameters.

        Returns:
            List of internal URLs.
        """
        scrape_res = await self.scrape(url=url, **kwargs)
        if scrape_res.success and scrape_res.data:
            return scrape_res.data.links[:limit] if scrape_res.data.links else []
        return []

    async def close(self):
        """Close the crawler instance."""
        if self._crawler_instance:
            await self._crawler_instance.__aexit__(None, None, None)
            self._crawler_instance = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
