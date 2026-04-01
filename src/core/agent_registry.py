"""Agent registry for dynamic agent discovery and management.

This module manages the registration, discovery, and coordination of agents
in the multi-agent orchestration system.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from .agent_protocol import AgentProtocol

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for managing and discovering agents dynamically.

    Provides functionality for:
    - Agent registration and deregistration
    - Capability-based agent discovery
    - Health monitoring and status tracking
    - Dynamic agent loading from modules
    """

    def __init__(self):
        """Initialize empty registry."""
        self._agents: dict[str, AgentProtocol] = {}
        self._capabilities: dict[str, set[str]] = {}  # capability -> set of agent names
        self._agent_modules: dict[str, str] = {}  # agent_name -> module_path

    def register(self, agent: AgentProtocol) -> None:
        """Register agent and index capabilities.

        Args:
            agent: Agent instance implementing AgentProtocol

        Raises:
            ValueError: If agent with same name already registered

        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")

        if not agent.config.enabled:
            logger.info(f"Skipping registration of disabled agent: {agent.name}")
            return

        self._agents[agent.name] = agent

        # Index capabilities for fast lookup
        for capability in agent.capabilities:
            if capability not in self._capabilities:
                self._capabilities[capability] = set()
            self._capabilities[capability].add(agent.name)

        logger.info(
            f"Registered agent '{agent.name}' with capabilities: {agent.capabilities}"
        )

    def deregister(self, agent_name: str) -> bool:
        """Deregister agent and cleanup capabilities index.

        Args:
            agent_name: Name of agent to deregister

        Returns:
            True if agent was deregistered, False if not found

        """
        if agent_name not in self._agents:
            return False

        agent = self._agents[agent_name]

        # Cleanup capability index
        for capability in agent.capabilities:
            if capability in self._capabilities:
                self._capabilities[capability].discard(agent_name)
                if not self._capabilities[capability]:
                    del self._capabilities[capability]

        # Cleanup agent
        del self._agents[agent_name]
        if agent_name in self._agent_modules:
            del self._agent_modules[agent_name]

        logger.info(f"Deregistered agent: {agent_name}")
        return True

    def get_agent(self, agent_name: str) -> AgentProtocol | None:
        """Get agent by name.

        Args:
            agent_name: Name of agent to retrieve

        Returns:
            Agent instance or None if not found

        """
        return self._agents.get(agent_name)

    def get_agent_for_capability(self, capability: str) -> AgentProtocol | None:
        """Find best agent for given capability.

        Args:
            capability: Required capability

        Returns:
            Best available agent for the capability or None

        """
        if capability not in self._capabilities:
            return None

        # Get all agents with this capability
        agent_names = self._capabilities[capability]

        # Filter for healthy and enabled agents
        available_agents = []
        for agent_name in agent_names:
            agent = self._agents[agent_name]
            health = agent.get_health_status()
            if health.get("healthy", False) and health.get("enabled", False):
                available_agents.append((agent, health))

        if not available_agents:
            return None

        # Simple selection: agent with lowest current task count
        best_agent = min(available_agents, key=lambda x: x[1].get("current_tasks", 0))[
            0
        ]

        return best_agent

    def get_agents_for_capabilities(
        self, capabilities: list[str]
    ) -> list[AgentProtocol]:
        """Find agents that can handle multiple capabilities.

        Args:
            capabilities: List of required capabilities

        Returns:
            List of agents that can handle all capabilities

        """
        if not capabilities:
            return []

        # Get agents for first capability
        candidate_agents = self._capabilities.get(capabilities[0], set()).copy()

        # Intersect with agents for each subsequent capability
        for capability in capabilities[1:]:
            if capability not in self._capabilities:
                return []
            candidate_agents.intersection_update(self._capabilities[capability])

        # Return healthy agents
        result = []
        for agent_name in candidate_agents:
            agent = self._agents[agent_name]
            health = agent.get_health_status()
            if health.get("healthy", False) and health.get("enabled", False):
                result.append(agent)

        return result

    def list_agents(self) -> list[AgentProtocol]:
        """Get list of all registered agents.

        Returns:
            List of all registered agent instances

        """
        return list(self._agents.values())

    def list_capabilities(self) -> list[str]:
        """Get list of all available capabilities.

        Returns:
            List of all capabilities across all agents

        """
        return list(self._capabilities.keys())

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all agents.

        Returns:
            Dictionary with registry and agent health information

        """
        agent_statuses = {}
        total_agents = len(self._agents)
        healthy_agents = 0

        for agent_name, agent in self._agents.items():
            status = agent.get_health_status()
            agent_statuses[agent_name] = status
            if status.get("healthy", False):
                healthy_agents += 1

        return {
            "registry_healthy": healthy_agents > 0,
            "total_agents": total_agents,
            "healthy_agents": healthy_agents,
            "unhealthy_agents": total_agents - healthy_agents,
            "total_capabilities": len(self._capabilities),
            "agents": agent_statuses,
        }

    def discover_agents(self, agents_module_path: str = "orchestration.agents") -> int:
        """Auto-discover and register available agents from module.

        Args:
            agents_module_path: Python module path containing agent classes

        Returns:
            Number of agents discovered and registered

        """
        discovered_count = 0

        try:
            # Import the agents module
            agents_module = importlib.import_module(agents_module_path)

            # Get all modules in the agents package
            if hasattr(agents_module, "__path__"):
                agents_dir = Path(agents_module.__path__[0])
                for module_file in agents_dir.glob("*.py"):
                    if module_file.name.startswith("__"):
                        continue

                    module_name = module_file.stem
                    full_module_path = f"{agents_module_path}.{module_name}"

                    discovered_count += self._discover_agents_in_module(
                        full_module_path
                    )

        except ImportError as e:
            logger.error(f"Failed to import agents module '{agents_module_path}': {e}")

        logger.info(f"Discovered and registered {discovered_count} agents")
        return discovered_count

    def _discover_agents_in_module(self, module_path: str) -> int:
        """Discover agents in a specific module.

        Args:
            module_path: Full module path to inspect

        Returns:
            Number of agents discovered in this module

        """
        discovered_count = 0

        try:
            module = importlib.import_module(module_path)

            # Look for classes that implement AgentProtocol
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    obj.__module__ == module_path
                    and hasattr(obj, "__annotations__")
                    and self._implements_agent_protocol(obj)
                ):
                    try:
                        # Try to instantiate and register
                        # This assumes agents have a default constructor or factory
                        if hasattr(obj, "create_default"):
                            agent_instance = obj.create_default()
                        else:
                            # Skip if we can't instantiate without parameters
                            continue

                        self.register(agent_instance)
                        self._agent_modules[agent_instance.name] = module_path
                        discovered_count += 1

                    except Exception as e:
                        logger.warning(
                            f"Failed to instantiate agent {name} from "
                            f"{module_path}: {e}"
                        )

        except ImportError as e:
            logger.warning(f"Failed to import module '{module_path}': {e}")

        return discovered_count

    def _implements_agent_protocol(self, cls) -> bool:
        """Check if a class implements the AgentProtocol.

        Args:
            cls: Class to check

        Returns:
            True if class implements AgentProtocol

        """
        try:
            # Check if all required methods are present
            required_methods = [
                "execute_task",
                "validate_task",
                "get_config",
                "get_health_status",
                "cleanup",
            ]
            for method in required_methods:
                if not hasattr(cls, method):
                    return False

            # Check if required attributes are present
            return hasattr(cls, "name") or (
                hasattr(cls, "__annotations__") and "name" in cls.__annotations__
            )

        except Exception:
            return False

    async def cleanup_all(self) -> None:
        """Cleanup all registered agents."""
        for agent in self._agents.values():
            try:
                await agent.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up agent {agent.name}: {e}")

        self._agents.clear()
        self._capabilities.clear()
        self._agent_modules.clear()
        logger.info("All agents cleaned up and registry cleared")
