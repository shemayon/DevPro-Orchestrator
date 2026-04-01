"""Modular agent implementations.

This package contains individual agent modules that implement the AgentProtocol
for the multi-agent orchestration system.
"""

from .coding_agent import CodingAgent
from .documentation_agent import DocumentationAgent
from .research_agent import ResearchAgent
from .testing_agent import TestingAgent

__all__ = [
    "CodingAgent",
    "DocumentationAgent",
    "ResearchAgent",
    "TestingAgent",
]
