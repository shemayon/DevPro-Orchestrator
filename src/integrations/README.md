# Exa and Crawl4AI Integration for LangGraph Agents

This module provides clean, async-compatible Python API wrappers for Exa (neural search) and Crawl4AI (local web scraping), specifically designed for integration with LangGraph agents and multi-agent workflows.

## Features

- **Direct API Access (Exa)**: High-quality neural and semantic search.
- **Local Scraping (Crawl4AI)**: Local Playwright-based web crawling without external API costs.
- **Unified Agent Protocol**: All integration responses align with the system's `AgentReport` schema.
- **Full Async/Await Support**: Optimized for LangGraph async non-blocking workflows.
- **Comprehensive Error Handling**: Built-in retries and robust exception management.
- **Cost Tracking (Exa)**: Monitoring for managed search expenses.

## Quick Start

### Installation

The required dependencies are already included in the project's `pyproject.toml`:

```bash
# Install project dependencies
uv install

# Install Playwright browsers (required for Crawl4AI)
playwright install chromium
```

### Environment Setup

Create a `.env` file in your project root:

```bash
# Required API keys
EXA_API_KEY=your_exa_api_key_here

# Optional Crawl4AI configuration
CRAWL4AI_HEADLESS=True
CRAWL4AI_TIMEOUT=30000
```

## API Clients Overview

### Exa Client Features

- **Neural Search**: Semantic search using embeddings to find high-relevance matches.
- **Keyword Search**: Traditional keyword-based search.
- **Research API**: Automated research tasks with synthesized structured output.
- **Content Extraction**: Retrieve full text and highlights from discovered URLs.

### Crawl4AI Client Features

- **Local Execution**: Playwright-based scraping running on your infrastructure.
- **LLM-Friendly Output**: Generates clean Markdown optimized for LLM consumption.
- **Structured Extraction**: Support for extracting JSON data using custom schemas.
- **Interaction Support**: Handle dynamic pages, JavaScript, and user interactions.

## Basic Usage Examples

### Exa Client

```python
import asyncio
from src.integrations import ExaClient

async def basic_exa_example():
    async with ExaClient() as client:
        # Semantic search
        results = await client.search(
            query="LangGraph framework documentation",
            search_type="neural",
            num_results=5,
            include_text=True,
        )
        
        print(f"Found {len(results.results)} results")
        for result in results.results:
            print(f"- {result.title}: {result.url}")

asyncio.run(basic_exa_example())
```

### Crawl4AI Client

```python
import asyncio
from src.integrations.crawl4ai_client import Crawl4AIClient

async def basic_crawl_example():
    client = Crawl4AIClient()
    # Local scraping doesn't require an external API
    result = await client.scrape("https://docs.langchain.com/docs/langgraph")
    
    if result.success:
        print(f"Title: {result.metadata.title}")
        print(f"Content preview: {result.markdown[:200]}")

asyncio.run(basic_crawl_example())
```

## LangGraph Integration

The system uses a `Supervisor` (powered by `langgraph-supervisor`) to orchestrate these tools.

```python
# The ResearchAgent automatically leverages these clients
research_agent = ResearchAgent()
# Use state-based execution
state = await research_agent.execute_task(current_state)
```

## Testing

Run the test suite to verify your configuration:

```bash
# Run all integration tests
uv run pytest tests/test_integrations.py -v

# Run agent orchestration tests
uv run pytest tests/test_langgraph_agents.py -v
```

## Best Practices

1. **Local Setup**: Ensure `playwright install chromium` is run in your environment.
2. **Key Security**: Never commit `.env` files with real API keys.
3. **Async Awareness**: Always use `await` when calling integration methods.
4. **Error Handling**: Check the `success` field in results before processing data.
