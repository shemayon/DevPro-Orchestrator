"""Research Agent for data collection and web scraping tasks.

This module implements a specialized agent for research and data collection
using Exa and Crawl4AI integration.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage

from ..core.agent_protocol import AgentConfig, AgentExecutionError, BaseAgent
from ..core.state import AgentState
from ..integrations.crawl4ai_client import Crawl4AIClient
from ..integrations.exa_client import ExaClient
from ..schemas import AgentReport, AgentType, TaskStatus

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Specialized agent for research and data collection tasks.

    Uses Exa and Crawl4AI for web research and scraping.
    Implements the AgentProtocol for consistent behavior.
    """

    def __init__(self, name: str | None = None, config: AgentConfig = None):
        """Initialize research agent with configuration and API clients."""
        if config is None:
            config = self._create_default_config()
            if name:
                config.name = name

        super().__init__(config)

        self.exa_client = ExaClient()
        self.crawl4ai_client = Crawl4AIClient()

    @classmethod
    def create_default(cls) -> "ResearchAgent":
        """Create a ResearchAgent with default configuration."""
        return cls()

    def _create_default_config(self) -> AgentConfig:
        """Create default configuration for research agent."""
        return AgentConfig(
            name="research",
            enabled=True,
            capabilities=[
                "web_scraping",
                "data_collection",
                "market_research",
                "information_synthesis",
                "api_exploration",
            ],
            model="exa-research-pro",
            timeout=120,
            retry_attempts=3,
            max_concurrent_tasks=2,
            tools=["exa_client", "crawl4ai_client"],
        )

    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute research task based on requirements."""
        if not state.get("task_data"):
            raise AgentExecutionError(
                self.name, state.get("task_id", 0), "No task data provided"
            )

        task_data = state["task_data"]
        task_id = task_data.get("id", state.get("task_id", 0))

        logger.info(f"ResearchAgent executing task {task_id}")

        self._increment_task_count()
        start_time = datetime.now()

        try:
            # Analyze task to determine research approach
            research_output = await self._conduct_research(task_data)

            # Duration calculation for potential future use in metrics
            # Create agent report using unified schema
            duration = (datetime.now() - start_time).total_seconds() / 60
            report = AgentReport(
                agent_name=AgentType.RESEARCH,
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                success=True,
                execution_time_minutes=duration,
                outputs=research_output,
                artifacts=research_output.get("artifacts", []),
                next_actions=research_output.get("next_actions", []),
                recommendations=[
                    "Review research findings for implementation insights",
                    "Identify specific technical requirements",
                ],
            )

            # Update state
            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = report.model_dump()

            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(
                HumanMessage(content=f"Research completed for task {task_id}")
            )

            logger.info(f"ResearchAgent completed task {task_id} successfully")

        except Exception as e:
            logger.error(f"Agent {self.name} failed task {task_id}: {e}", exc_info=True)
            duration = (datetime.now() - start_time).total_seconds() / 60
            report = AgentReport(
                agent_name=AgentType.RESEARCH,
                task_id=task_id,
                status=TaskStatus.FAILED,
                success=False,
                execution_time_minutes=duration,
                outputs={"error": str(e)},
                artifacts=[],
                issues_found=[str(e)],
                error_details=str(e),
            )
            
            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = report.model_dump()
            return state

        finally:
            self._decrement_task_count()

        return state

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate if this agent can handle the research task."""
        if not await super().validate_task(task_data):
            return False

        # Check for research-specific requirements
        if not task_data:
            return False

        # Research agent can handle tasks with research keywords
        research_keywords = [
            "research",
            "data",
            "collect",
            "scrape",
            "analyze",
            "investigate",
            "explore",
            "gather",
            "information",
        ]

        task_text = (
            task_data.get("title", "")
            + " "
            + task_data.get("description", "")
            + " "
            + task_data.get("component_area", "")
        ).lower()

        return any(keyword in task_text for keyword in research_keywords)

    async def _conduct_research(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Conduct research based on task requirements."""
        title = task_data.get("title", "")
        description = task_data.get("description", "")
        component_area = task_data.get("component_area", "")

        research_results = {
            "research_type": "web_search",
            "queries_performed": [],
            "sources_found": [],
            "key_findings": [],
            "artifacts": [],
            "next_actions": [],
        }

        # Determine research queries based on task
        queries = self._generate_research_queries(title, description, component_area)

        for query in queries:
            # Use Exa for neural search
            search_results = await self.exa_client.search(
                query=query,
                search_type="neural",
                num_results=5,
                include_text=True,
                include_summary=True,
            )

            research_results["queries_performed"].append(query)

            for result in search_results.results:
                source_info = {
                    "title": result.title,
                    "url": result.url,
                    "summary": result.summary,
                    "relevance_score": result.score,
                }
                research_results["sources_found"].append(source_info)

                if result.text and len(result.text) > 100:
                    # Extract key findings from content
                    findings = self._extract_key_findings(result.text, query)
                    research_results["key_findings"].extend(findings)

        # Generate next action recommendations
        research_results["next_actions"] = [
            "Review research findings for implementation insights",
            "Identify specific technical requirements",
            "Plan implementation approach based on findings",
        ]

        return research_results

    def _generate_research_queries(
        self, title: str, description: str, component_area: str
    ) -> list[str]:
        """Generate relevant research queries for the task."""
        queries = []

        # Base query from title
        if title:
            queries.append(title)

        # Component-specific queries
        if component_area:
            queries.append(f"{component_area} best practices")
            queries.append(f"{component_area} implementation guide")

        # Extract key terms from description
        if description:
            # Simple keyword extraction (could be enhanced with NLP)
            keywords = [
                word
                for word in description.lower().split()
                if len(word) > 4 and word.isalpha()
            ]
            if keywords:
                queries.append(" ".join(keywords[:3]))

        return queries[:3]  # Limit to 3 queries to manage costs

    def _extract_key_findings(self, text: str, query: str) -> list[str]:
        """Extract key findings from research text."""
        # Simple extraction based on sentence relevance
        sentences = text.split(". ")
        query_words = set(query.lower().split())

        findings = []
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words.intersection(sentence_words))

            if overlap >= 1 and len(sentence) > 20:
                findings.append(sentence.strip())

        return findings[:3]  # Return top 3 relevant findings

    async def cleanup(self) -> None:
        """Cleanup research agent resources."""
        await super().cleanup()
        # Close any persistent connections if needed
        # self.exa_client.close() if it had such a method
        # self.firecrawl_client.close() if it had such a method
        logger.info("ResearchAgent cleanup completed")
