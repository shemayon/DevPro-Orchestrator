# 🧪 DevPro Orchestrator Agent Testing Guide

This guide provides actionable examples to test the specialized capabilities of each expert agent within the DevPro Orchestrator MAS. Use these examples in the **Dashboard UI** to verify tool integration and autonomous orchestration.

## 🚀 How to Test
1. Open the Dashboard UI.
2. Click **+ New Task**.
3. Copy the **Title**, **Description**, and **Component** from the examples below.
4. Hit **Create Task**, then click **Execute** once the task appears in the Lifecycle Management table.

---

## 🔍 1. Research Expert
**Goal**: Verify neural web search (**Exa**) and high-fidelity scraping (**Crawl4AI**).

- **Task Title**: `Research LangGraph Multi-Agent Patterns`
- **Description**: `Search for the latest best practices and design patterns for building multi-agent systems using LangGraph. Then, scrape a high-relevance technical blog post to summarize the key architectural takeaways.`
- **Component**: `Research`
- **Expected Outcome**: The agent should call `web_search` to find relevant links and then use `scrape_website` to extract content from one of the results.

---

## 🧑‍💻 2. Coding Expert
**Goal**: Verify autonomous code generation and structural analysis.

- **Task Title**: `Implement JSON Schema Validator Utility`
- **Description**: `Create a Python utility named 'utils/json_validator.py' that can validate nested JSON objects against a provided schema using Pydantic. The utility should include basic error handling for malformed data.`
- **Component**: `Core`
- **Expected Outcome**: The agent should generate the Python code, call `write_code` to save the file, and potentially `analyze_code` to verify its complexity.

---

## 🧪 3. Testing Expert
**Goal**: Verify test suite generation and automated execution.

- **Task Title**: `Generate Tests for JSON Validator`
- **Description**: `Create a comprehensive pytest suite for the 'utils/json_validator.py' utility. Include test cases for valid schemas, invalid data types, and missing required fields. Execute the tests and report the results.`
- **Component**: `Testing`
- **Expected Outcome**: The agent should generate test code, call `create_test` to save it, and then trigger `run_tests` using the project's pytest environment.

---

## 📚 4. Documentation Expert
**Goal**: Verify technical writing and API documentation capabilities.

- **Task Title**: `Generate Backend API Guide`
- **Description**: `Analyze the 'src/api.py' file to identify all available endpoints, request models, and response structures. Generate a comprehensive API documentation guide in Markdown format and save it to 'docs/API_REFERENCE.md'.`
- **Component**: `Documentation`
- **Expected Outcome**: The agent should call `generate_api_docs` to extract endpoint metadata and then use `write_documentation` to save the final markdown file.

---

## 🛠️ Advanced Orchestration Test
To test the **Supervisor's** ability to delegate and coordinate multiple agents, try a "Chain of Command" task:

- **Task Title**: `Research and Document New Feature Design`
- **Description**: `First, research current industry standards for OAuth2 implementation in FastAPI. Then, create a technical specification document in 'docs/OAUTH_SPEC.md' outlining how we should implement it in our system.`
- **Component**: `Integrations`
- **Expected Outcome**: The Supervisor should first delegate research to the **Research Expert** and then hand off the findings to the **Documentation Expert** to create the specification.

---
> **Tip**: Monitor the agent status in the "Agent Network" section of the dashboard to see them move to ACTIVE during execution.
