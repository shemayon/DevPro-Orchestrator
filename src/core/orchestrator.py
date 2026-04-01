"""Modular Multi-Agent Orchestrator.

This module implements the main orchestration logic using the agent registry
and dynamic agent discovery for managing multi-agent workflows.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

# Dynamic imports to avoid circular dependencies - agents imported in methods
from ..agents.coding_agent import CodingAgent
from ..agents.documentation_agent import DocumentationAgent
from ..agents.research_agent import ResearchAgent
from ..agents.testing_agent import TestingAgent
from ..task_manager import TaskManager
from .agent_registry import AgentRegistry
from .state import AgentState

logger = logging.getLogger(__name__)


class ModularOrchestrator:
    """Main orchestrator class that coordinates the multi-agent system.

    Uses the agent registry for dynamic agent discovery and management.
    Manages workflow execution, batch processing, and agent coordination.
    """

    def __init__(
        self,
        config_path: str | None = None,
        openai_api_key: str | None = None,
        openrouter_api_key: str | None = None,
        db_path: str | None = None,
    ):
        """Initialize the modular orchestrator."""
        # Load configuration
        self.config = self._load_configuration(config_path)

        # Initialize supervisor with OpenAI o3
        self.supervisor_client = ChatOpenAI(
            model=self.config.get("orchestrator", {}).get("supervisor_model", "o3"),
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY"),
            temperature=0.1,
        )

        # Initialize agent registry
        self.agent_registry = AgentRegistry()

        # Initialize task manager
        self.task_manager = TaskManager(db_path)

        # Setup agents and workflow
        self._initialize_agents(openrouter_api_key)
        self.workflow = self._create_workflow()

        logger.info("ModularOrchestrator initialized successfully")

    def _load_configuration(self, config_path: str | None = None) -> dict[str, Any]:
        """Load orchestrator configuration from YAML file."""
        if config_path is None:
            # Default configuration path
            config_path = Path(__file__).parent.parent / "config" / "orchestrator.yaml"

        try:
            # Use Path.open() for better path handling and Ruff compliance
            with Path(config_path).open(encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.warning(
                f"Configuration file not found at {config_path}, using defaults"
            )
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration when config file is not available."""
        return {
            "orchestrator": {
                "supervisor_model": "o3",
                "batch_processing": {
                    "enabled": True,
                    "max_batch_size": 10,
                    "max_parallel_tasks": 4,
                },
                "coordination": {
                    "task_assignment_strategy": "capability_based",
                    "max_task_retries": 3,
                },
            }
        }

    def _initialize_agents(self, openrouter_api_key: str | None = None):
        """Initialize and register all agents."""
        try:
            # Create agent instances with proper configuration
            research_agent = ResearchAgent.create_default()
            coding_agent = CodingAgent.create_default()
            testing_agent = TestingAgent.create_default()
            documentation_agent = DocumentationAgent.create_default()

            # Register agents
            self.agent_registry.register(research_agent)
            self.agent_registry.register(coding_agent)
            self.agent_registry.register(testing_agent)
            self.agent_registry.register(documentation_agent)

            logger.info(f"Registered {len(self.agent_registry.list_agents())} agents")

        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise

    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for multi-agent coordination."""
        # Create state graph
        workflow = StateGraph(AgentState)

        # Add supervisor node
        workflow.add_node("supervisor", self._analyze_and_delegate_task)

        # Add agent nodes dynamically based on registry
        for agent in self.agent_registry.list_agents():
            workflow.add_node(agent.name, agent.execute_task)

        # Add coordination and finalization nodes
        workflow.add_node("coordinate", self._coordinate_agents)
        workflow.add_node("finalize", self._finalize_task)

        # Define routing logic
        def route_to_agent(state: AgentState) -> str:
            """Route to appropriate agent based on supervisor decision."""
            next_agent = state.get("next_agent")

            # Check if the agent exists in registry
            if next_agent and self.agent_registry.get_agent(next_agent):
                return next_agent

            return "finalize"

        def should_coordinate(state: AgentState) -> str:
            """Determine if coordination is needed."""
            agent_outputs = state.get("agent_outputs", {})

            # Check for blocking or assistance needs
            for output in agent_outputs.values():
                if isinstance(output, dict):
                    status = output.get("status")
                    if status in ["blocked", "requires_assistance"]:
                        return "coordinate"

            return "finalize"

        # Add edges
        workflow.add_edge(START, "supervisor")
        workflow.add_conditional_edges("supervisor", route_to_agent)

        # Agent outputs go to coordination check
        for agent in self.agent_registry.list_agents():
            workflow.add_conditional_edges(agent.name, should_coordinate)

        workflow.add_conditional_edges("coordinate", route_to_agent)
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _analyze_and_delegate_task(self, state: AgentState) -> AgentState:
        """Analyze task and delegate to appropriate agent."""
        task_data = state.get("task_data")
        if not task_data:
            logger.error("No task data provided for analysis")
            state["error_context"] = {"supervisor_error": "No task data provided"}
            return state

        task_id = task_data.get("id", 0)
        logger.info(f"Supervisor analyzing task {task_id}")

        try:
            # Get available agents and their capabilities
            available_agents = self.agent_registry.list_agents()
            agent_info = {}

            for agent in available_agents:
                health = agent.get_health_status()
                if health.get("healthy", False) and health.get("enabled", False):
                    agent_info[agent.name] = {
                        "capabilities": agent.capabilities,
                        "current_tasks": health.get("current_tasks", 0),
                        "max_concurrent": health.get("max_concurrent_tasks", 1),
                    }

            # Determine best agent for the task
            assigned_agent = await self._determine_best_agent(task_data, agent_info)

            if assigned_agent:
                state["next_agent"] = assigned_agent
                state["coordination_context"]["assigned_agent"] = assigned_agent
                state["coordination_context"]["assignment_reasoning"] = (
                    f"Selected {assigned_agent} based on capabilities and availability"
                )

                logger.info(f"Task {task_id} assigned to {assigned_agent}")
            else:
                logger.warning(f"No suitable agent found for task {task_id}")
                state["error_context"] = {
                    "supervisor_error": "No suitable agent available"
                }
                state["next_agent"] = None

        except Exception as e:
            logger.error(f"Error in task analysis: {e}")
            state["error_context"] = {"supervisor_error": str(e)}
            state["next_agent"] = None

        return state

    async def _determine_best_agent(
        self, task_data: dict[str, Any], agent_info: dict[str, Any]
    ) -> str | None:
        """Determine the best agent for a given task."""
        # Simple heuristic-based assignment for now
        # Could be enhanced with ML-based assignment later

        task_text = (
            task_data.get("title", "")
            + " "
            + task_data.get("description", "")
            + " "
            + task_data.get("component_area", "")
        ).lower()

        # Score agents based on capability match and availability
        agent_scores = {}

        for agent_name, info in agent_info.items():
            score = 0
            capabilities = info["capabilities"]

            # Check capability matches
            for capability in capabilities:
                if any(
                    keyword in task_text for keyword in capability.lower().split("_")
                ):
                    score += 10

            # Prefer agents with lower current load
            current_tasks = info["current_tasks"]
            max_concurrent = info["max_concurrent"]

            if current_tasks < max_concurrent:
                load_factor = 1 - (current_tasks / max_concurrent)
                score += load_factor * 5
            else:
                score = 0  # Agent at capacity

            agent_scores[agent_name] = score

        # Return agent with highest score
        if agent_scores:
            best_agent = max(agent_scores.items(), key=lambda x: x[1])
            if best_agent[1] > 0:
                return best_agent[0]

        return None

    async def _coordinate_agents(self, state: AgentState) -> AgentState:
        """Coordinate between agents when assistance is needed."""
        logger.info("Coordinating agents for assistance")

        agent_outputs = state.get("agent_outputs", {})
        coordination_context = state.get("coordination_context", {})

        # Find agents that need assistance
        blocked_agents = []
        for agent_name, output in agent_outputs.items():
            if isinstance(output, dict) and output.get("status") in [
                "blocked",
                "requires_assistance",
            ]:
                blocked_agents.append(agent_name)

        if blocked_agents:
            # For now, simple coordination: try to reassign to another agent
            for blocked_agent in blocked_agents:
                logger.info(
                    f"Agent {blocked_agent} needs assistance, attempting reassignment"
                )

                # Try to find alternative agent
                task_data = state.get("task_data", {})
                alternative_agent = await self._find_alternative_agent(
                    task_data, blocked_agent
                )

                if alternative_agent:
                    state["next_agent"] = alternative_agent
                    coordination_context["reassigned_from"] = blocked_agent
                    coordination_context["reassigned_to"] = alternative_agent
                    logger.info(
                        f"Reassigned task from {blocked_agent} to {alternative_agent}"
                    )
                    break

        state["coordination_context"] = coordination_context
        return state

    async def _find_alternative_agent(
        self, task_data: dict[str, Any], blocked_agent: str
    ) -> str | None:
        """Find an alternative agent when the assigned agent is blocked."""
        # Get available agents excluding the blocked one
        available_agents = []
        for agent in self.agent_registry.list_agents():
            if agent.name != blocked_agent:
                health = agent.get_health_status()
                if health.get("healthy", False) and health.get("enabled", False):
                    # Normalize and guard against malformed values
                    try:
                        current = int(health.get("current_tasks", 0))
                    except (TypeError, ValueError):
                        current = 0

                    try:
                        max_concurrent = int(health.get("max_concurrent_tasks", 1))
                    except (TypeError, ValueError):
                        max_concurrent = 1

                    # Enforce sane lower bounds
                    current = max(current, 0)
                    max_concurrent = max(max_concurrent, 1)

                    if current < max_concurrent:
                        available_agents.append(agent)

        # Try to validate task with available agents
        for agent in available_agents:
            try:
                if await agent.validate_task(task_data):
                    return agent.name
            except Exception as e:
                logger.warning(f"Error validating task with agent {agent.name}: {e}")

        return None

    async def _finalize_task(self, state: AgentState) -> AgentState:
        """Finalize task execution and update database."""
        task_id = state.get("task_id")
        agent_outputs = state.get("agent_outputs", {})

        logger.info(f"Finalizing task {task_id}")

        # Determine overall task status
        overall_status = "completed"

        for output in agent_outputs.values():
            if isinstance(output, dict):
                status = output.get("status", "unknown")
                if status == "failed":
                    overall_status = "failed"
                    break
                elif status in ["blocked", "requires_assistance"]:
                    overall_status = "requires_attention"

        # Update task in database
        try:
            await self._update_task_status(task_id, overall_status, agent_outputs)
        except Exception as e:
            logger.error(f"Error updating task status: {e}")

        # Add completion message
        if "messages" not in state:
            state["messages"] = []
        state["messages"].append(
            HumanMessage(
                content=f"Task {task_id} finalized with status: {overall_status}"
            )
        )

        return state

    async def _update_task_status(
        self, task_id: int, status: str, agent_outputs: dict[str, Any]
    ):
        """Update task status in database."""
        # This would integrate with the existing TaskManager
        # For now, just log the completion
        logger.info(f"Task {task_id} completed with status: {status}")
        logger.debug(f"Agent outputs summary: {list(agent_outputs.keys())}")

    async def execute_task(self, task_id: int) -> dict[str, Any]:
        """Execute a single task through the multi-agent workflow."""
        logger.info(f"Starting modular execution for task {task_id}")

        # Get task data from database
        task_data = self._get_task_data(task_id)
        if not task_data:
            raise ValueError(f"Task {task_id} not found")

        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=f"Executing task {task_id}")],
            "task_id": task_id,
            "task_data": task_data,
            "agent_outputs": {},
            "batch_id": None,
            "coordination_context": {},
            "error_context": None,
            "next_agent": None,
        }

        try:
            # Execute workflow
            final_state = await self.workflow.ainvoke(initial_state)

            # Extract results
            result = {
                "task_id": task_id,
                "status": "completed"
                if not final_state.get("error_context")
                else "failed",
                "agent_outputs": final_state.get("agent_outputs", {}),
                "coordination_context": final_state.get("coordination_context", {}),
                "execution_time": datetime.now().isoformat(),
            }

            if final_state.get("error_context"):
                result["error_context"] = final_state["error_context"]

            logger.info(f"Task {task_id} execution completed")
            return result

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "execution_time": datetime.now().isoformat(),
            }

    def _get_task_data(self, task_id: int) -> dict[str, Any] | None:
        """Get task data from database."""
        # This would integrate with the existing TaskManager
        # For now, return a mock task for testing
        return {
            "id": task_id,
            "title": f"Task {task_id}",
            "description": f"Description for task {task_id}",
            "component_area": "general",
            "success_criteria": "Task should be completed successfully",
        }

    async def execute_batch(
        self, task_ids: list[int], batch_size: int | None = None
    ) -> dict[str, Any]:
        """Execute multiple tasks in batch mode."""
        if batch_size is None:
            batch_size = (
                self.config.get("orchestrator", {})
                .get("batch_processing", {})
                .get("max_batch_size", 10)
            )

        logger.info(f"Starting batch execution of {len(task_ids)} tasks")

        # Process tasks in batches
        results = []
        for i in range(0, len(task_ids), batch_size):
            batch = task_ids[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self.execute_task(task_id) for task_id in batch],
                return_exceptions=True,
            )
            results.extend(batch_results)

        # Summarize results
        successful = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "completed"
        )
        failed = len(results) - successful

        return {
            "batch_size": len(task_ids),
            "successful": successful,
            "failed": failed,
            "results": results,
            "execution_time": datetime.now().isoformat(),
        }

    def get_agent_health_status(self) -> dict[str, Any]:
        """Get health status of all registered agents."""
        return self.agent_registry.get_health_status()

    async def cleanup(self):
        """Cleanup orchestrator resources."""
        logger.info("Cleaning up orchestrator resources")
        await self.agent_registry.cleanup_all()
        logger.info("Orchestrator cleanup completed")
