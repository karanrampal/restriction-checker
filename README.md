# Restriction Checker

Restriction Checker is a tool designed to analyze images for restricted items. It features a **Streamlit** frontend and a **FastAPI** backend that downloads images from a given URL and leverages Google's **Gemini** models to determine if the image contains restricted content.

## Architecture

1. **Frontend (`src/app.py`)**: A Streamlit application where users can input image URLs, and seamlessly navigate their past interactions via a persistent chat history sidebar.
2. **Backend API (`src/api/`)**: A FastAPI service that securely processes requests, downloads the target image as bytes, and communicates with the AI agent.
3. **AI Agent (`src/agents/`)**: Interfaces with the Gemini LLM using adk library to analyze the image content and produce a structured output (JSON).
4. **Storage (`src/data_processing/`)**: Connects to Google Cloud Storage to maintain a session-based history for easy reference.
5. **Infrastructure (`terraform/`)**: Infrastructure-as-code configuration for deploying to Google Cloud (Cloud Run, Artifact Registry, Cloud Storage).

## Project Structure

```text
restriction-checker/
├── configs/            # Configuration files (config.yaml)
├── scripts/            # Deployment and run scripts
├── src/
│   ├── app.py          # Streamlit frontend entrypoint
│   ├── check_agent.py  # Entrypoint to test adk agents
│   ├── agents/         # Gemini API integration and prompts
│   ├── api/            # FastAPI routes, dependencies, and models
│   ├── core/           # App configuration and logging
│   └── data_processing/# Image downloading and byte processing
├── terraform/          # GCP infrastructure configurations
├── tests/              # Unit, integration, and performance tests
├── Dockerfile          # Container definition
├── Makefile            # Useful development commands
└── pyproject.toml      # Python dependencies and tool configs (using uv)
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for fast Python dependency management.
- GCP Credentials (if deploying or running against live Google Vertex/Gemini models)
- Make (for running `Makefile` commands)

## Local Development Setup

1. **Install Dependencies**
   
   This project uses `uv` for blazing-fast package management.
   ```bash
   make install-all
   ```

2. **Environment Variables**
   
   Ensure you have the necessary environment variables set (e.g., Gemini API keys, API Base URLs). You can set these up in a `.env` file or export them directly.
   
   Example contents of a `.env` file:
   ```bash
   export GOOGLE_CLOUD_PROJECT="restrictor-check-345e"
   #export GOOGLE_CLOUD_LOCATION="europe-west1"
   export GOOGLE_CLOUD_LOCATION="global"
   export GOOGLE_GENAI_USE_VERTEXAI=TRUE
   ```

   Then you can runt he command `source .env`  to export these variables.

3. **Running the FastAPI Backend**
   ```bash
   uv run fastapi dev src/api/app.py --port 8080
   ```

4. **Running the Streamlit Frontend**
   ```bash
   uv run streamlit run src/app.py --server.port 8000 --server.address 0.0.0.0
   ```

## Development & Testing

`make` targets are provided for linting, formatting, and testing.

- **`make format`**: Format code (runs `ruff`)
- **`make typecheck`**: Type checking (runs `mypy`)
- **`make lint`**: Lint code (runs `pylint`)
- **`make test`**: Run unit tests
- **`make test-int`**: Run integration tests
- **`make test-perf`**: Run performance benchmarks
- **`make precommit`**: Formats, lints, typechecks, and tests

## Deployment

The application is containerized using Docker and deployed via Google Cloud Run, provisioned through Terraform. 

Both the **FastAPI backend** and **Streamlit frontend** are hosted as separate Cloud Run services. To ensure security:
- **Frontend Access**: Protected and authenticated using **Identity-Aware Proxy (IAP)**.
- **Service Communication**: Backend access from the frontend is secured using Google Cloud **Identity and Access Management (IAM)**.

### Infrastructure (Terraform)
Navigate to the `terraform/` directory to manage GCP resources (Artifact Registry, Cloud Storage, Cloud Run). `.tfvars` files are used to manage environments (e.g., `dev.tfvars`, `prod.tfvars`).

### Build and Push (Docker)
You can use the Makefile to build and push the container to Google Cloud Artifact Registry:
```bash
make docker-bp DOCKERFILE=Dockerfile VERSION=latest
```

### Deployment Scripts
Helper scripts are located in `scripts/`:
- `run_tf.sh`: Wrapper for Terraform commands.
- `deploy_cr.sh`: General helper script to deploy services to Google Cloud Run.
- `deploy_app.sh`: Deploy the restrictor api and app on Cloud Run
- `check_api.sh`: Test the deployed API.
