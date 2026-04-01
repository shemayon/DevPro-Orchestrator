"""Coding Agent for implementation and development tasks.

This module implements a specialized agent for code generation,
bug fixes, and feature development using OpenRouter horizon-beta.
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
from ..schemas import AgentReport, AgentType, TaskStatus

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """Specialized agent for implementation and development tasks.

    Handles code generation, bug fixes, and feature development.
    Implements the AgentProtocol for consistent behavior.
    """

    def __init__(
        self,
        name: str | None = None,
        config: AgentConfig = None,
        openrouter_api_key: str | None = None,
    ):
        """Initialize coding agent with configuration and OpenRouter client."""
        if config is None:
            config = self._create_default_config()
            if name:
                config.name = name

        super().__init__(config)

        self.openrouter_client = ChatOpenAI(
            model="openrouter/horizon-beta",  # Using OpenRouter horizon-beta
            api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.2,
        )

    @classmethod
    def create_default(cls) -> "CodingAgent":
        """Create a CodingAgent with default configuration."""
        return cls()

    def _create_default_config(self) -> AgentConfig:
        """Create default configuration for coding agent."""
        return AgentConfig(
            name="coding",
            enabled=True,
            capabilities=[
                "implementation",
                "debugging",
                "code_generation",
                "refactoring",
                "code_review",
            ],
            model="openrouter/horizon-beta",
            timeout=180,
            retry_attempts=2,
            max_concurrent_tasks=1,
            tools=[],
        )

    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute coding task based on requirements."""
        if not state.get("task_data"):
            raise AgentExecutionError(
                self.name, state.get("task_id", 0), "No task data provided"
            )

        task_data = state["task_data"]
        task_id = task_data.get("id", state.get("task_id", 0))

        logger.info(f"CodingAgent executing task {task_id}")

        self._increment_task_count()
        start_time = datetime.now()

        try:
            # Generate implementation based on task requirements
            implementation_output = await self._generate_implementation(
                task_data, state
            )

            duration = (datetime.now() - start_time).total_seconds() / 60

            # Create agent report
            report = AgentReport(
                agent_name=AgentType.CODING,
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                success=True,
                execution_time_minutes=duration,
                outputs=implementation_output,
                artifacts=implementation_output.get("files_created", []),
                recommendations=[
                    "Test implementation",
                    "Code review",
                    "Integration testing",
                ],
            )

            # Update state
            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = report.model_dump()

            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(
                HumanMessage(content=f"Implementation completed for task {task_id}")
            )

            logger.info(f"CodingAgent completed task {task_id} successfully")

        except Exception as e:
            from ..schemas.unified_models import AgentReport, TaskStatus
            logger.error(f"CodingAgent error: {e}")
            duration = (datetime.now() - start_time).total_seconds() / 60

            error_report = AgentReport(
                agent_name=AgentType.CODING,
                task_id=task_id,
                status=TaskStatus.FAILED,
                success=False,
                execution_time_minutes=duration,
                outputs={"error": str(e)},
                issues_found=[str(e)],
                error_details=str(e),
            )

            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = error_report.model_dump()
            return state
            state["error_context"] = {"coding_error": str(e)}

            raise AgentExecutionError(self.name, task_id, str(e), e) from e

        finally:
            self._decrement_task_count()

        return state

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate if this agent can handle the coding task."""
        if not await super().validate_task(task_data):
            return False

        # Check for coding-specific requirements
        if not task_data:
            return False

        # Coding agent can handle tasks with coding keywords
        coding_keywords = [
            "implement",
            "code",
            "develop",
            "build",
            "create",
            "fix",
            "debug",
            "refactor",
            "refactor",
            "optimize",
            "generate",
        ]

        task_text = (
            task_data.get("title", "")
            + " "
            + task_data.get("description", "")
            + " "
            + task_data.get("component_area", "")
        ).lower()

        return any(keyword in task_text for keyword in coding_keywords)

    async def _generate_implementation(
        self, task_data: dict[str, Any], state: AgentState
    ) -> dict[str, Any]:
        """Generate implementation based on task requirements."""
        # Get research context if available
        research_context = ""
        agent_outputs = state.get("agent_outputs", {})
        if "research" in agent_outputs:
            research_output = agent_outputs["research"].get("output", {})
            key_findings = research_output.get("key_findings", [])
            if key_findings:
                research_context = "\n".join(key_findings[:3])

        # Create implementation prompt
        implementation_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a senior software engineer specializing in Python
                    development.
                    Create clean, maintainable implementations following best practices.

            Guidelines:
            - Use type hints and docstrings
            - Follow SOLID principles
            - Include error handling
            - Write modular, testable code
            - Use async/await for I/O operations
            """,
                ),
                (
                    "human",
                    """Implement the following task:

            Title: {title}
            Description: {description}
            Component Area: {component_area}
            Success Criteria: {success_criteria}

            Research Context: {research_context}

            Provide implementation as structured response with:
            1. Code files with full implementation
            2. Key design decisions
            3. Dependencies required
            4. Integration notes
            """,
                ),
            ]
        )

        try:
            response = await self.openrouter_client.ainvoke(
                implementation_prompt.format_messages(
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    component_area=task_data.get("component_area", ""),
                    success_criteria=task_data.get("success_criteria", ""),
                    research_context=research_context
                    or "No research context available",
                )
            )

            implementation_content = response.content

            # Parse implementation response
            implementation_output = {
                "implementation_type": "code_generation",
                "content": implementation_content,
                "files_created": self._extract_files_from_response(
                    implementation_content
                ),
                "design_decisions": self._extract_design_decisions(
                    implementation_content
                ),
                "dependencies": self._extract_dependencies(implementation_content),
                "integration_notes": self._extract_integration_notes(
                    implementation_content
                ),
            }

            return implementation_output

        except Exception as e:
            logger.error(f"Implementation generation failed: {e}")
            return {
                "implementation_type": "error",
                "error": str(e),
                "files_created": [],
                "design_decisions": [],
                "dependencies": [],
                "integration_notes": [],
            }

    def _extract_files_from_response(self, content: str) -> list[str]:
        """Extract file names from implementation response."""
        # Simple extraction - look for file patterns
        file_patterns = [
            r"```python\s*#\s*([^\n]+\.py)",
            r"File:\s*([^\n]+\.py)",
            r"Create\s+file:\s*([^\n]+\.py)",
        ]

        files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            files.extend(matches)

        return list(set(files))  # Remove duplicates

    def _extract_design_decisions(self, content: str) -> list[str]:
        """Extract design decisions from implementation response."""
        # Look for decision-related sections
        decisions = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if any(
                keyword in line.lower()
                for keyword in ["decision", "approach", "design"]
            ):
                # Collect next few lines as decision context
                decision_text = []
                for j in range(i, min(i + 3, len(lines))):
                    if lines[j].strip():
                        decision_text.append(lines[j].strip())

                if decision_text:
                    decisions.append(" ".join(decision_text))

        return decisions[:3]  # Limit to 3 key decisions

    def _extract_dependencies(self, content: str) -> list[str]:
        """Extract dependencies from implementation response."""
        # Look for import statements and dependency mentions
        dependencies = []

        # Extract from import statements
        import_patterns = [
            r"from\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"import\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"pip install\s+([a-zA-Z0-9\-_]+)",
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            dependencies.extend(matches)

        # Filter out standard library modules
        external_deps = []
        for dep in dependencies:
            if dep not in ["os", "sys", "json", "datetime", "asyncio", "logging"]:
                external_deps.append(dep)

        return list(set(external_deps))  # Remove duplicates

    def _extract_integration_notes(self, content: str) -> list[str]:
        """Extract integration notes from implementation response."""
        notes = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if (
                any(
                    keyword in line.lower()
                    for keyword in ["integration", "usage", "note"]
                )
                and i + 1 < len(lines)
                and lines[i + 1].strip()
            ):
                notes.append(lines[i + 1].strip())

        return notes[:3]  # Limit to 3 key notes

    async def cleanup(self) -> None:
        """Cleanup coding agent resources."""
        await super().cleanup()
        # Close any persistent connections if needed
        logger.info("CodingAgent cleanup completed")
