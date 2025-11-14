# GCP Testing Agent

This repository contains the `gcp-testing-agent`, a production-grade, AI-powered agent designed to perform automated integration testing for Google Cloud deployments. The agent is built using the Google Cloud Agent Development Kit (ADK) and is deployed to the managed Vertex AI Agent Engine.

This agent acts as the intelligent "brain" in an autonomous software development lifecycle (SDLC). It receives natural language testing instructions from a higher-level agent (like a GitHub-based "Test Organizer"), executes those instructions by interacting with live Google Cloud services, and reports back a definitive `PASSED` or `FAILED` status.

---

## 🚀 Features

-   **AI-Powered Reasoning**: Uses a powerful LLM (e.g., Gemini 1.5 Pro) to understand complex, natural language test plans.
-   **Tool-Based Architecture**: Interacts with Google Cloud services via a secure, extensible set of tools.
-   **Production-Ready**: Built with the official Google Cloud Agent Starter Pack, ensuring a robust, scalable, and maintainable architecture.
-   **Automated CI/CD**: Deployed via a fully automated GitHub Actions workflow that manages infrastructure with Terraform.
-   **Serverless**: Runs on the managed and scalable Vertex AI Agent Engine.

---

## 🏗️ Architecture

This agent is one component of a larger multi-agent system:

1.  **Test Organizer Agent (GitHub)**: Analyzes pull requests and creates natural language test instructions.
2.  **MCP Server (`gcp-mcp-server`)**: A lightweight Cloud Function that acts as a protocol bridge, receiving MCP requests from the GitHub agent.
3.  **This Agent (`gcp-testing-agent`)**: The core testing engine. It receives the proxied request from the MCP server, interprets the instructions, and uses its tools to perform the validation.

```mermaid
graph TD
    A[GitHub Agent<br>(Test Organizer)] -- MCP Request --> B(MCP Server<br>Cloud Function);
    B -- Agent Engine API Call --> C{GCP Testing Agent<br>(This Repository)};
    C -- Use Tools --> D[GCS Tools];
    C -- Use Tools --> E[Logging Tools];
    D -- Read/List --> F[(GCS Bucket)];
    E -- Query --> G[(Cloud Logging)];
```

---

## 🛠️ Development

This project was generated from the `adk_base` template of the `agent-starter-pack`.

### Prerequisites

-   Python 3.11+
-   `pipx` (for isolated tool installation)
-   Google Cloud SDK (`gcloud`)
-   Terraform

### Environment Setup

1. Create a virtual environment using Python 3.12:

   ```cmd
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```cmd
   # Install pip-tools for dependency management
   python -m pip install pip-tools==7.3.0
   
   # Compile requirements from requirements.in
   pip-compile requirements.in --output-file requirements.txt
   
   # Install all dependencies
   python -m pip install -r requirements.txt
   ```

2.  **Define the Agent (`src/agent.py`)**:
    The core agent logic, instruction prompt, and tool registration are defined in `src/agent.py`.

3.  **Implement Tools (`src/tools/`)**:
    Tools are standard Python functions decorated with `@tool` from the ADK. Each tool should have a clear purpose, a descriptive docstring (which the agent uses for reasoning), and strong type hints.

    *   **`gcs_tools.py`**: Contains tools for interacting with Google Cloud Storage.
    *   **`logging_tools.py`**: Contains tools for querying Cloud Logging.

4.  **Local Testing**:
    You can run the agent locally for rapid development and testing.
    ```bash
    # Run the local development server
    make run

    # In a separate terminal, send a query to the agent
    curl -X POST http://localhost:8080/query -H "Content-Type: application/json" -d '{"message": "Check for files in the my-bucket/outputs/ folder."}'
    ```

---

## 🚀 Deployment

Deployment is fully automated via the CI/CD pipeline configured by the `agent-starter-pack`.

### Initial Setup

1.  **Run the Setup Wizard**:
    From the root of the repository, run the one-time setup command. This will configure your GCP projects, create service accounts, set up Workload Identity Federation, and generate the GitHub Actions workflows.
    ```bash
    agent-starter-pack setup-cicd
    ```
    Follow the interactive prompts. You will need at least two GCP project IDs (for staging and production) and the necessary permissions.

2.  **Commit and Push**:
    The wizard will create and modify several files. Commit these to your repository and push to the `main` branch.
    ```bash
    git add .
    git commit -m "feat: configure CI/CD pipeline"
    git push
    ```

### Automated Deployment Workflow

-   **On Pull Request**: The `pr-checks.yml` workflow runs unit and integration tests.
-   **On Push to `main`**: The `deploy.yml` workflow is triggered.
    1.  It authenticates to Google Cloud using Workload Identity Federation.
    2.  It runs `terraform apply` to provision or update the infrastructure (including the Agent Engine).
    3.  It builds and pushes the agent's container image to Artifact Registry.
    4.  It deploys the new agent version to the Agent Engine.

After a successful deployment, the `AGENT_ENGINE_ID` will be available in the workflow logs. This ID is required for the `gcp-mcp-server` to connect to this agent.

---

## ⚙️ Configuration

-   **Agent Definition**: `src/agent.py`
-   **Tools**: `src/tools/`
-   **Infrastructure**: `terraform/`
-   **CI/CD Pipeline**: `.github/workflows/`

## 🤝 Contributing

1.  Create a new branch.
2.  Make your changes (e.g., add a new tool in the `src/tools/` directory).
3.  Add the new tool to the `tools` list in `src/agent.py`.
4.  Write unit tests for your new tool.
5.  Open a pull request. The automated `pr-checks` workflow will run.
6.  Upon merging, the `deploy` workflow will automatically deploy the updated agent.

