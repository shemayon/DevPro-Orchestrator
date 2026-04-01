#!/usr/bin/env python3
"""Modern Multi-Agent Supervisor Implementation using langgraph-supervisor library.

This module provides a clean, modern supervisor implementation that coordinates
specialized agents through the official langgraph-supervisor library.

Key benefits:
- Replaces 500+ lines of custom supervisor logic with library calls
- Uses proven langgraph-supervisor patterns for agent coordination
- Maintains full type safety with Pydantic integration
- Supports multi-level hierarchical supervision
- Provides advanced handoff and forwarding capabilities
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langgraph_supervisor import create_supervisor

from .schemas import TaskStatus
from .task_manager import TaskManager

logger = logging.getLogger(__name__)


class Supervisor:
    """Modern multi-agent supervisor using langgraph-supervisor library.

    This class coordinates specialized agents through the official
    langgraph-supervisor library, providing:
    - Agent delegation and coordination
    - Workflow management
    - State persistence
    - Error handling and recovery

    Benefits:
    - 85%+ code reduction vs custom implementation
    - Battle-tested library patterns
    - Enhanced reliability and maintenance
    - Advanced features like hierarchical supervision
    """

    def __init__(self, openai_api_key: str | None = None, db_path: str | None = None):
        """Initialize the multi-agent supervisor."""
        # Initialize core components
        self.model = ChatOpenAI(
            model="gpt-4o",  # Using gpt-4o as recommended by library
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY"),
            temperature=0.1,
        )

        self.task_manager = TaskManager(db_path)

        # Initialize persistence components
        self.checkpointer = InMemorySaver()
        self.store = InMemoryStore()

        # Create specialized agents using library patterns
        self._initialize_agents()

        # Create supervisor workflow using library
        self.app = self._create_supervisor_workflow()

    def _initialize_agents(self):
        """Initialize specialized agents with library-compatible interfaces."""
        # Create tools for each agent type
        self.research_tools = self._create_research_tools()
        self.coding_tools = self._create_coding_tools()
        self.testing_tools = self._create_testing_tools()
        self.documentation_tools = self._create_documentation_tools()

        # Create library-compatible agents using create_react_agent
        self.research_agent = create_react_agent(
            model=self.model,
            tools=self.research_tools,
            name="research_expert",
            prompt=(
                "You are a world-class research expert specializing in web scraping, "
                "data collection, and competitive analysis. Use your tools to gather "
                "comprehensive information and provide detailed research reports."
            ),
        )

        self.coding_agent = create_react_agent(
            model=self.model,
            tools=self.coding_tools,
            name="coding_expert",
            prompt=(
                "You are an expert software engineer specializing in Python "
                "development, code generation, and implementation. Write clean, "
                "maintainable, well-documented code following best practices."
            ),
        )

        self.testing_agent = create_react_agent(
            model=self.model,
            tools=self.testing_tools,
            name="testing_expert",
            prompt=(
                "You are a testing expert specializing in unit tests, integration "
                "tests, and quality assurance. Create comprehensive test suites with "
                "high coverage and robust error handling."
            ),
        )

        self.documentation_agent = create_react_agent(
            model=self.model,
            tools=self.documentation_tools,
            name="documentation_expert",
            prompt=(
                "You are a documentation expert specializing in technical writing, "
                "API documentation, and user guides. Create clear, comprehensive "
                "documentation that helps users understand and use the system."
            ),
        )

    def _create_research_tools(self) -> list[Any]:
        """Create tools for research agent."""
        from .integrations.crawl4ai_client import Crawl4AIClient
        from .integrations.exa_client import ExaClient

        def web_search(query: str) -> str:
            """Search the web for information using Exa."""
            client = ExaClient()
            try:
                results = client.search_and_contents(query, num_results=5)
                return str(results) if results else "No results found"
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                return f"Search failed: {e!s}"

        def scrape_website(url: str) -> str:
            """Scrape website content using Crawl4AI."""
            client = Crawl4AIClient()
            try:
                # Use synchronous-looking interface if available or run async
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(client.scrape(url))
                return (
                    result.data.markdown
                    if result and result.success
                    else f"Scraping failed: {result.error if result else 'Unknown error'}"
                )
            except Exception as e:
                logger.error(f"Website scraping failed: {e}")
                return f"Scraping failed: {e!s}"
            finally:
                loop.run_until_complete(client.close())

        return [web_search, scrape_website]

    def _create_coding_tools(self) -> list[Any]:
        """Create tools for coding agent."""

        def write_code(filename: str, content: str) -> str:
            """Write code to a file."""
            try:
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
                with Path(filename).open("w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote code to {filename}"
            except Exception as e:
                return f"Failed to write code: {e!s}"

        def analyze_code(code: str) -> str:
            """Analyze code for quality and potential issues."""
            # Simplified code analysis - in practice, use tools like ruff, mypy
            lines = len(code.splitlines())
            functions = code.count("def ")
            classes = code.count("class ")
            return (
                "Code analysis: "
                f"{lines} lines, {functions} functions, {classes} classes"
            )

        return [write_code, analyze_code]

    def _create_testing_tools(self) -> list[Any]:
        """Create tools for testing agent."""

        def run_tests(test_path: str) -> str:
            """Run tests using pytest."""
            import subprocess
            import sys

            try:
                # Use the exact Python interpreter running this process to avoid PATH
                # issues and satisfy Ruff's requirement against partial executable paths
                cmd = [sys.executable, "-m", "pytest", test_path, "-v"]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    shell=False,  # explicit for clarity and safety
                )
                return f"Test results:\n{result.stdout}\n{result.stderr}"
            except Exception as e:
                return f"Test execution failed: {e!s}"

        def create_test(test_name: str, test_content: str) -> str:
            """Create a test file."""
            filename = f"test_{test_name}.py"
            try:
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
                with Path(filename).open("w", encoding="utf-8") as f:
                    f.write(test_content)
                return f"Successfully created test file: {filename}"
            except Exception as e:
                return f"Failed to create test: {e!s}"

        return [run_tests, create_test]

    def _create_documentation_tools(self) -> list[Any]:
        """Create tools for documentation agent."""

        def write_documentation(filename: str, content: str) -> str:
            """Write documentation to a file."""
            try:
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
                with Path(filename).open("w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote documentation to {filename}"
            except Exception as e:
                return f"Failed to write documentation: {e!s}"

        def generate_api_docs(code_path: str) -> str:
            """Generate API documentation from code."""
            # Simplified - in practice, use tools like pydoc, sphinx
            try:
                code = Path(code_path).read_text(encoding="utf-8")
                functions = [
                    line.strip()
                    for line in code.splitlines()
                    if line.strip().startswith("def ")
                ]
                return f"API documentation for {code_path}:\n" + "\n".join(functions)
            except Exception as e:
                return f"Failed to generate API docs: {e!s}"

        return [write_documentation, generate_api_docs]

    def _create_supervisor_workflow(self):
        """Create supervisor workflow using langgraph-supervisor library."""
        # Create supervisor with all specialized agents
        workflow = create_supervisor(
            agents=[
                self.research_agent,
                self.coding_agent,
                self.testing_agent,
                self.documentation_agent,
            ],
            model=self.model,
            prompt=(
                "You are a team supervisor managing specialized experts: "
                "research_expert, coding_expert, testing_expert, and "
                "documentation_expert. "
                "\n\nAgent Specializations:"
                "\n- research_expert: Web scraping, data collection, market research"
                "\n- coding_expert: Python development, code generation, implementation"
                "\n- testing_expert: Unit tests, integration tests, quality assurance"
                "\n- documentation_expert: Technical writing, API docs, user guides"
                "\n\nDelegate tasks based on their requirements and agent expertise."
            ),
            # Configure supervisor behavior
            output_mode="full_history",  # Include full message history
            add_handoff_messages=True,  # Include handoff messages for transparency
        )

        # Compile with persistence
        return workflow.compile(checkpointer=self.checkpointer, store=self.store)

    async def execute_task(self, task_id: int) -> dict[str, Any]:
        """Execute a task using the library supervisor.

        Args:
            task_id: ID of the task to execute

        Returns:
            Execution results with agent reports and final state

        Raises:
            ValueError: If task is not found
            Exception: If there is an error during task execution

        """
        try:
            # Get task from database
            task = self.task_manager.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Update task status to in progress
            self.task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)

            # Create execution message
            user_message = self._format_task_message(task)

            # Execute using library supervisor
            result = await self.app.ainvoke(
                {"messages": [HumanMessage(content=user_message)]},
                config={"configurable": {"thread_id": f"task_{task_id}"}},
            )

            # Update task status based on results
            success = self._analyze_execution_results(result)
            new_status = TaskStatus.COMPLETED if success else TaskStatus.BLOCKED
            self.task_manager.update_task_status(task_id, new_status)

            return {
                "task_id": task_id,
                "status": new_status.value,
                "success": success,
                "messages": result.get("messages", []),
                "execution_time": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            self.task_manager.update_task_status(task_id, TaskStatus.BLOCKED)

            return {
                "task_id": task_id,
                "status": TaskStatus.BLOCKED.value,
                "success": False,
                "error": str(e),
                "execution_time": datetime.now().isoformat(),
            }

    def _format_task_message(self, task: Any) -> str:
        """Format task into a clear message for the supervisor."""
        # Handle both enum and string values for priority and complexity
        priority_str = (
            task.priority.value
            if hasattr(task.priority, "value")
            else str(task.priority)
        )
        complexity_str = (
            task.complexity.value
            if hasattr(task.complexity, "value")
            else str(task.complexity)
        )

        return (
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Component Area: {task.component_area}\n"
            f"Priority: {priority_str}\n"
            f"Complexity: {complexity_str}\n"
            f"Success Criteria: {task.success_criteria}\n"
            f"Time Estimate: {task.time_estimate_hours} hours\n"
            f"\nPlease delegate this task to the appropriate agent "
            f"and coordinate execution."
        )

    def _analyze_execution_results(self, result: dict[str, Any]) -> bool:
        """Analyze execution results to determine success."""
        messages = result.get("messages", [])
        if not messages:
            return False

        # Enhanced heuristic for library-based supervisor
        success_indicators = ["completed", "finished", "success", "done"]
        error_indicators = ["error", "failed", "exception", "blocked"]

        # 1. Check all messages for any success indicator
        has_success = False
        for msg in messages:
            content = ""
            if hasattr(msg, "content"):
                content = str(msg.content).lower()
            else:
                content = str(msg).lower()
            
            if any(ind in content for ind in success_indicators):
                has_success = True
                break

        # 2. Check last message for errors
        has_error = False
        if messages:
            last_msg = messages[-1]
            last_content = str(last_msg.content).lower() if hasattr(last_msg, "content") else str(last_msg).lower()
            has_error = any(indicator in last_content for indicator in error_indicators)

        return has_success and not has_error

    async def execute_batch(self, task_ids: list[int]) -> list[dict[str, Any]]:
        """Execute multiple tasks in batch using the supervisor."""
        results = []

        for task_id in task_ids:
            try:
                result = await self.execute_task(task_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch task {task_id} failed: {e}")
                results.append(
                    {
                        "task_id": task_id,
                        "status": TaskStatus.BLOCKED.value,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def get_workflow_state(self, thread_id: str) -> dict[str, Any]:
        """Get current workflow state for a thread."""
        try:
            state = self.app.get_state({"configurable": {"thread_id": thread_id}})
            return {
                "thread_id": thread_id,
                "values": state.values,
                "next": list(state.next) if state.next else [],
                "created_at": state.created_at.isoformat()
                if state.created_at
                else None,
                "updated_at": state.updated_at.isoformat()
                if state.updated_at
                else None,
            }
        except Exception as e:
            logger.error(f"Failed to get workflow state: {e}")
            return {"error": str(e)}

    def list_active_threads(self) -> list[str]:
        """List all active workflow threads."""
        try:
            # This would need to be implemented based on checkpointer capabilities
            # For now, return empty list as InMemorySaver doesn't expose this
            return []
        except Exception as e:
            logger.error(f"Failed to list threads: {e}")
            return []

    async def close(self) -> None:
        """Cleanup resources and close connections."""
        try:
            # Cleanup any resources if needed
            # For now, just log the cleanup
            logger.info("Supervisor cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def get_agent_status(self) -> dict[str, Any]:
        """Get status information for all agents and system."""
        try:
            # Get task statistics from task manager
            all_tasks = self.task_manager.get_tasks_by_status("all")
            completed_tasks = [t for t in all_tasks if t.get("status") == "completed"]
            in_progress_tasks = [
                t for t in all_tasks if t.get("status") == "in_progress"
            ]
            blocked_tasks = [t for t in all_tasks if t.get("status") == "blocked"]
            not_started_tasks = [
                t for t in all_tasks if t.get("status") == "not_started"
            ]

            total_hours = sum(
                t.get("time_estimate_hours", 0)
                for t in all_tasks
                if t.get("time_estimate_hours")
            )
            remaining_hours = sum(
                t.get("time_estimate_hours", 0)
                for t in all_tasks
                if t.get("status") not in ["completed"] and t.get("time_estimate_hours")
            )

            completion_percentage = (
                len(completed_tasks) / len(all_tasks) * 100 if all_tasks else 0
            )

            return {
                "system_status": "active" if self.app else "inactive",
                "last_updated": datetime.now().isoformat(),
                "agents": {
                    "research_expert": {
                        "status": "active",
                        "tools": ["web_search", "scrape_website"],
                    },
                    "coding_expert": {
                        "status": "active",
                        "tools": ["write_code", "analyze_code"],
                    },
                    "testing_expert": {
                        "status": "active",
                        "tools": ["run_tests", "create_test"],
                    },
                    "documentation_expert": {
                        "status": "active",
                        "tools": ["write_documentation", "generate_api_docs"],
                    },
                },
                "task_statistics": {
                    "total_tasks": len(all_tasks),
                    "completed_tasks": len(completed_tasks),
                    "in_progress_tasks": len(in_progress_tasks),
                    "blocked_tasks": len(blocked_tasks),
                    "not_started_tasks": len(not_started_tasks),
                    "completion_percentage": completion_percentage,
                    "total_estimated_hours": total_hours,
                    "remaining_hours": remaining_hours,
                },
            }
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {
                "system_status": "error",
                "last_updated": datetime.now().isoformat(),
                "error": str(e),
                "agents": {},
                "task_statistics": {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "in_progress_tasks": 0,
                    "blocked_tasks": 0,
                    "not_started_tasks": 0,
                    "completion_percentage": 0,
                    "total_estimated_hours": 0,
                    "remaining_hours": 0,
                },
            }
