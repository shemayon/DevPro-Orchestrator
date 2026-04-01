"""Documentation Agent for technical writing and reporting tasks.

This module implements a specialized agent for creating comprehensive
documentation, guides, and reports using OpenRouter horizon-beta.
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


class DocumentationAgent(BaseAgent):
    """Specialized agent for documentation and reporting tasks.

    Creates comprehensive documentation, guides, and reports.
    Implements the AgentProtocol for consistent behavior.
    """

    def __init__(
        self, config: AgentConfig = None, openrouter_api_key: str | None = None
    ):
        """Initialize documentation agent with configuration and OpenRouter client."""
        if config is None:
            config = self._create_default_config()

        super().__init__(config)

        self.openrouter_client = ChatOpenAI(
            model="openrouter/horizon-beta",
            api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.3,
        )

    @classmethod
    def create_default(cls) -> "DocumentationAgent":
        """Create a DocumentationAgent with default configuration."""
        return cls()

    def _create_default_config(self) -> AgentConfig:
        """Create default configuration for documentation agent."""
        return AgentConfig(
            name="documentation",
            enabled=True,
            capabilities=[
                "documentation_generation",
                "content_creation",
                "technical_writing",
                "readme_creation",
                "api_documentation",
            ],
            model="openrouter/horizon-beta",
            timeout=120,
            retry_attempts=2,
            max_concurrent_tasks=2,
            tools=[],
        )

    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute documentation task based on requirements."""
        if not state.get("task_data"):
            raise AgentExecutionError(
                self.name, state.get("task_id", 0), "No task data provided"
            )

        task_data = state["task_data"]
        task_id = task_data.get("id", state.get("task_id", 0))

        logger.info(f"DocumentationAgent executing task {task_id}")

        self._increment_task_count()
        start_time = datetime.now()

        try:
            # Generate documentation based on all agent outputs
            documentation_output = await self._create_documentation(task_data, state)

            duration = (datetime.now() - start_time).total_seconds() / 60

            # Create agent report
            report = AgentReport(
                agent_name=self.name,
                task_id=task_id,
                status="completed",
                output=documentation_output,
                duration_minutes=duration,
                artifacts_created=documentation_output.get("documentation_files", []),
                next_recommended_actions=[
                    "Review documentation",
                    "Update user guides",
                    "Publish documentation",
                ],
            )

            # Update state
            if "agent_outputs" not in state:
                state["agent_outputs"] = {}
            state["agent_outputs"][self.name] = report.model_dump()

            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(
                HumanMessage(content=f"Documentation completed for task {task_id}")
            )

            logger.info(f"DocumentationAgent completed task {task_id} successfully")

        except Exception as e:
            logger.error(f"DocumentationAgent error: {e}")
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
            state["error_context"] = {"documentation_error": str(e)}

            raise AgentExecutionError(self.name, task_id, str(e), e) from e

        finally:
            self._decrement_task_count()

        return state

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate if this agent can handle the documentation task."""
        if not await super().validate_task(task_data):
            return False

        # Check for documentation-specific requirements
        if not task_data:
            return False

        # Documentation agent can handle tasks with documentation keywords
        documentation_keywords = [
            "document",
            "documentation",
            "readme",
            "guide",
            "manual",
            "report",
            "write",
            "content",
            "api",
            "spec",
            "specification",
        ]

        task_text = (
            task_data.get("title", "")
            + " "
            + task_data.get("description", "")
            + " "
            + task_data.get("component_area", "")
        ).lower()

        return any(keyword in task_text for keyword in documentation_keywords)

    async def _create_documentation(
        self, task_data: dict[str, Any], state: AgentState
    ) -> dict[str, Any]:
        """Create comprehensive documentation based on all agent outputs."""
        # Collect context from all agents
        context_summary = self._build_context_summary(state)

        # Create documentation prompt
        documentation_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a technical writer specializing in software
                    documentation.
                    Create clear, comprehensive documentation that is useful for
                    developers and users.

            Guidelines:
            - Use clear, concise language
            - Include code examples where relevant
            - Structure with appropriate headings
            - Add usage instructions and best practices
            - Include troubleshooting information
            """,
                ),
                (
                    "human",
                    """Create documentation for the following completed task:

            Title: {title}
            Description: {description}
            Component Area: {component_area}
            Success Criteria: {success_criteria}

            Agent Outputs Summary: {context_summary}

            Provide comprehensive documentation including:
            1. Overview and purpose
            2. Implementation details
            3. Usage instructions
            4. API/interface documentation
            5. Testing information
            6. Troubleshooting guide
            """,
                ),
            ]
        )

        try:
            response = await self.openrouter_client.ainvoke(
                documentation_prompt.format_messages(
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    component_area=task_data.get("component_area", ""),
                    success_criteria=task_data.get("success_criteria", ""),
                    context_summary=context_summary,
                )
            )

            documentation_content = response.content

            # Parse documentation response
            documentation_output = {
                "documentation_type": "comprehensive_guide",
                "content": documentation_content,
                "documentation_files": self._extract_documentation_files(
                    documentation_content
                ),
                "sections": self._extract_sections(documentation_content),
                "code_examples": self._extract_code_examples(documentation_content),
                "links_and_references": self._extract_references(documentation_content),
            }

            return documentation_output

        except Exception as e:
            logger.error(f"Documentation generation failed: {e}")
            return {
                "documentation_type": "error",
                "error": str(e),
                "documentation_files": [],
                "sections": [],
                "code_examples": [],
                "links_and_references": [],
            }

    def _build_context_summary(self, state: AgentState) -> str:
        """Build summary of all agent outputs for documentation context."""
        agent_outputs = state.get("agent_outputs", {})
        summary_parts = []

        for agent_name, output in agent_outputs.items():
            if isinstance(output, dict) and "output" in output:
                agent_output = output["output"]
                status = output.get("status", "unknown")

                summary_parts.append(f"{agent_name.title()} Agent ({status}):")

                # Add key information from each agent
                if agent_name == "research":
                    findings = agent_output.get("key_findings", [])
                    if findings:
                        summary_parts.append(
                            f"  - Key findings: {'; '.join(findings[:2])}"
                        )

                elif agent_name == "coding":
                    files = agent_output.get("files_created", [])
                    if files:
                        summary_parts.append(
                            f"  - Files created: {', '.join(files[:3])}"
                        )
                    decisions = agent_output.get("design_decisions", [])
                    if decisions:
                        summary_parts.append(
                            f"  - Design decisions: {'; '.join(decisions[:1])}"
                        )

                elif agent_name == "testing":
                    test_files = agent_output.get("test_files", [])
                    if test_files:
                        summary_parts.append(
                            f"  - Test files: {', '.join(test_files[:2])}"
                        )
                    categories = agent_output.get("test_categories", [])
                    if categories:
                        summary_parts.append(f"  - Test types: {', '.join(categories)}")

                summary_parts.append("")  # Empty line for readability

        return "\n".join(summary_parts)

    def _extract_documentation_files(self, content: str) -> list[str]:
        """Extract documentation file names from response."""
        file_patterns = [
            r"README\.md",
            r"[A-Z][a-zA-Z0-9_-]*\.md",
            r"File:\s*([^\n]*\.md)",
            r"Create\s+file:\s*([^\n]*\.md)",
        ]

        files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            files.extend(matches)

        return list(set(files))

    def _extract_sections(self, content: str) -> list[str]:
        """Extract main sections from documentation content."""
        # Look for markdown headers
        headers = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        return headers[:10]  # Limit to 10 main sections

    def _extract_code_examples(self, content: str) -> list[str]:
        """Extract code examples from documentation."""
        # Look for code blocks
        code_blocks = re.findall(r"```[\w]*\n(.*?)\n```", content, re.DOTALL)
        return [block.strip() for block in code_blocks[:5]]  # Limit to 5 examples

    def _extract_references(self, content: str) -> list[str]:
        """Extract links and references from documentation."""
        # Look for markdown links and references
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        references = [f"{text}: {url}" for text, url in links]

        # Look for plain URLs
        urls = re.findall(r"https?://[^\s]+", content)
        references.extend(urls)

        return list(set(references))[:10]  # Limit to 10 references

    async def cleanup(self) -> None:
        """Cleanup documentation agent resources."""
        await super().cleanup()
        # Close any persistent connections if needed
        logger.info("DocumentationAgent cleanup completed")
