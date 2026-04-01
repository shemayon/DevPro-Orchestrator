"""Testing Agent for quality assurance and validation tasks.

This module implements a specialized agent for test design, execution,
and quality assurance using OpenRouter horizon-beta.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ..core.agent_protocol import AgentConfig, AgentExecutionError, BaseAgent
from ..core.state import AgentState
from ..schemas import AgentReport

logger = logging.getLogger(__name__)


class TestingAgent(BaseAgent):
    """Specialized agent for testing and validation tasks.

    Creates tests, runs validation, and ensures quality.
    Implements the AgentProtocol for consistent behavior.
    """

    def __init__(
        self, config: AgentConfig = None, openrouter_api_key: str | None = None
    ):
        """Initialize testing agent with configuration and OpenRouter client."""
        if config is None:
            config = self._create_default_config()

        super().__init__(config)

        self.openrouter_client = ChatOpenAI(
            model="openrouter/horizon-beta",
            api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
        )

    @classmethod
    def create_default(cls) -> "TestingAgent":
        """Create a TestingAgent with default configuration."""
        return cls()

    def _create_default_config(self) -> AgentConfig:
        """Create default configuration for testing agent."""
        return AgentConfig(
            name="testing",
            enabled=True,
            capabilities=[
                "test_design",
                "test_execution",
                "quality_assurance",
                "validation",
                "performance_testing",
            ],
            model="openrouter/horizon-beta",
            timeout=150,
            retry_attempts=2,
            max_concurrent_tasks=1,
            tools=[],
        )

    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute testing task based on requirements."""
        if not state.get("task_data"):
            raise AgentExecutionError(
                self.name, state.get("task_id", 0), "No task data provided"
            )

        task_data = state["task_data"]
        task_id = task_data.get("id", state.get("task_id", 0))

        logger.info(f"TestingAgent executing task {task_id}")

        self._increment_task_count()
        start_time = datetime.now()

        try:
            # Generate tests based on implementation
            testing_output = await self._create_tests(task_data, state)

            duration = (datetime.now() - start_time).total_seconds() / 60

            # Create agent report
            report = AgentReport(
                agent_name=self.name,
                task_id=task_id,
                status="completed",
                output=testing_output,
                duration_minutes=duration,
                artifacts_created=testing_output.get("test_files", []),
                next_recommended_actions=[
                    "Run test suite",
                    "Code coverage analysis",
                    "Performance testing",
                ],
            )

            # Update state
            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = report.model_dump()

            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(
                HumanMessage(content=f"Testing completed for task {task_id}")
            )

            logger.info(f"TestingAgent completed task {task_id} successfully")

        except Exception as e:
            logger.error(f"TestingAgent error: {e}")
            duration = (datetime.now() - start_time).total_seconds() / 60

            error_report = AgentReport(
                agent_name=self.name,
                task_id=task_id,
                status="failed",
                output={"error": str(e)},
                duration_minutes=duration,
                blocking_issues=[str(e)],
            )

            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = error_report.model_dump()
            state["error_context"] = {"testing_error": str(e)}

            raise AgentExecutionError(self.name, task_id, str(e), e) from e

        finally:
            self._decrement_task_count()

        return state

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate if this agent can handle the testing task."""
        if not await super().validate_task(task_data):
            return False

        # Check for testing-specific requirements
        if not task_data:
            return False

        # Testing agent can handle tasks with testing keywords
        testing_keywords = [
            "test",
            "testing",
            "validate",
            "validation",
            "verify",
            "quality",
            "qa",
            "check",
            "coverage",
            "benchmark",
        ]

        task_text = (
            task_data.get("title", "")
            + " "
            + task_data.get("description", "")
            + " "
            + task_data.get("component_area", "")
        ).lower()

        return any(keyword in task_text for keyword in testing_keywords)

    async def _create_tests(
        self, task_data: dict[str, Any], state: AgentState
    ) -> dict[str, Any]:
        """Create comprehensive tests for the implementation."""
        # Get implementation context
        implementation_context = ""
        agent_outputs = state.get("agent_outputs", {})
        if "coding" in agent_outputs:
            coding_output = agent_outputs["coding"].get("output", {})
            implementation_context = coding_output.get("content", "")

        # Create testing prompt
        testing_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a QA engineer specializing in Python testing.
            Create comprehensive test suites using pytest and best practices.

            Guidelines:
            - Write unit tests, integration tests, and edge case tests
            - Use pytest fixtures and parametrization
            - Include async test support
            - Test error conditions and edge cases
            - Provide clear test documentation
            """,
                ),
                (
                    "human",
                    """Create tests for the following task:

            Title: {title}
            Description: {description}
            Success Criteria: {success_criteria}

            Implementation Context: {implementation_context}

            Provide comprehensive test suite with:
            1. Unit tests for core functionality
            2. Integration tests for component interaction
            3. Edge case and error condition tests
            4. Performance tests if applicable
            5. Test data and fixtures
            """,
                ),
            ]
        )

        try:
            response = await self.openrouter_client.ainvoke(
                testing_prompt.format_messages(
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    success_criteria=task_data.get("success_criteria", ""),
                    implementation_context=implementation_context
                    or "No implementation context available",
                )
            )

            test_content = response.content

            # Parse testing response
            testing_output = {
                "testing_type": "comprehensive_test_suite",
                "content": test_content,
                "test_files": self._extract_test_files(test_content),
                "test_categories": self._categorize_tests(test_content),
                "coverage_requirements": self._extract_coverage_requirements(
                    test_content
                ),
                "test_data": self._extract_test_data(test_content),
            }

            return testing_output

        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            return {
                "testing_type": "error",
                "error": str(e),
                "test_files": [],
                "test_categories": [],
                "coverage_requirements": [],
                "test_data": [],
            }

    def _extract_test_files(self, content: str) -> list[str]:
        """Extract test file names from response."""
        file_patterns = [
            r"test_[a-zA-Z0-9_]+\.py",
            r"File:\s*([^\n]*test[^\n]*\.py)",
            r"```python\s*#\s*([^\n]*test[^\n]*\.py)",
        ]

        files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            files.extend(matches)

        return list(set(files))

    def _categorize_tests(self, content: str) -> list[str]:
        """Categorize the types of tests created."""
        categories = []
        content_lower = content.lower()

        if "unit test" in content_lower or "def test_" in content_lower:
            categories.append("unit_tests")
        if "integration" in content_lower:
            categories.append("integration_tests")
        if "async" in content_lower or "await" in content_lower:
            categories.append("async_tests")
        if "performance" in content_lower or "benchmark" in content_lower:
            categories.append("performance_tests")
        if "fixture" in content_lower or "@pytest.fixture" in content:
            categories.append("test_fixtures")

        return categories

    def _extract_coverage_requirements(self, content: str) -> list[str]:
        """Extract coverage requirements from test content."""
        requirements = []
        lines = content.split("\n")

        for line in lines:
            if "coverage" in line.lower() or "test coverage" in line.lower():
                requirements.append(line.strip())

        return requirements

    def _extract_test_data(self, content: str) -> list[str]:
        """Extract test data requirements from content."""
        test_data = []
        lines = content.split("\n")

        for line in lines:
            if (
                any(
                    keyword in line.lower()
                    for keyword in ["test_data", "fixture", "sample"]
                )
                and line.strip()
                and not line.strip().startswith("#")
            ):
                test_data.append(line.strip())

        return test_data[:5]  # Limit to 5 key data items

    async def cleanup(self) -> None:
        """Cleanup testing agent resources."""
        await super().cleanup()
        # Close any persistent connections if needed
        logger.info("TestingAgent cleanup completed")
