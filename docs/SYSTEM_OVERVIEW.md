# 🌌 DevPro Orchestrator MAS System Overview

**DevPro Orchestrator MAS** is an advanced, production-ready multi-agent orchestration platform designed for autonomous task execution and research. It leverages **LangGraph** to coordinate specialized agents with a focus on high-fidelity, type-safe operations.

## 🏛️ High-Level Architecture

DevPro Orchestrator is built on a modular, decoupled architecture consisting of four main layers:

1.  **Dashboard Layer (UI)**: A React-based, high-fidelity monitoring interface that communicates with the backend via Nginx reverse proxy.
2.  **API Layer (Backend)**: A FastAPI server that manages the task lifecycle, agent status, and provides the RESTful entry point for orchestration.
3.  **Orchestration Layer (LangGraph)**: The "brain" of the system. A supervisor-led graph that routes tasks to expert nodes based on capability detection.
4.  **Integration Layer (Connectors)**: High-speed clients for external services like **Crawl4AI** (local browser automation) and **Exa** (neural web search).

---

## 🤖 Specialized Expert Agents

DevPro Orchestrator orchestrates a group of four specialized agents:

- **🔍 Research Expert**: Performs deep, recursive web research using a combination of semantic search (**Exa**) and high-fidelity local scraping (**Crawl4AI**).
- **🧑‍💻 Coding Expert**: Implements complex features, refactors codebases, and provides code audits with precision.
- **🧪 Testing Expert**: Generates comprehensive unit and integration tests, ensuring stability across the development lifecycle.
- **📚 Documentation Expert**: Translates complex technical logic into human-readable documentation and API specifications.

---

## 🔄 The Agentic Lifecycle

1.  **Task Creation**: A task is submitted via the UI with specific metadata (priority, component area, success criteria).
2.  **Supervisor Analysis**: The LangGraph Supervisor analyzes the task and routes it to the most capable expert agent.
3.  **Autonomous Execution**: The selected agent uses its specific tools (e.g., `web_search`, `write_code`) to complete the task.
4.  **Verification & Feedback**: The supervisor reviews the output and either requests refinements or marks the task as `COMPLETED`.
5.  **Persistence**: Every state change, progress note, and final artifact is persisted to the **DevPro Core Database** (SQLite/SQLModel).

---

## 🛠️ Technical Stack

- **Languge**: Python 3.12+ / Javascript (ES6+)
- **Frameworks**: FastAPI, React (Vite)
- **Orchestration**: LangGraph, LangChain
- **Validation**: Pydantic v2 (is_instance_of, computed_fields)
- **Infrastructure**: Docker, Nginx, SQLite
- **Scraping Engine**: Crawl4AI (Playwright-based)

---

> **DevPro Orchestrator: Bringing Autonomous Orchestration to Production Workflows.**
