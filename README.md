# AI CI Debugger

### *Autonomous Analysis Engine for DevOps*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go)](https://go.dev/)
[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat&logo=docker)](https://www.docker.com/)

**AI CI Debugger** is an event-driven, microservices-based AI agent designed to monitor GitHub Actions, diagnose CI/CD failures using LLMs (Llama 3.1 via Groq), and post actionable fixes directly back to GitHub commits.

---

## Key Features

- **Instant Analysis**: Automated diagnosis within seconds of job failure.
- **Deep Contextual Awareness**: Analyzes **code diffs**, **full manifests** (`go.mod`, `requirements.txt`, etc.), and the **culprit files** (through failing logs) to understand the root cause.
- **Actionable Fixes**: Provides specific code suggestions directly in GitHub commit comments.
- **Long-term Memory (RAG)**: Utilizes a vector database to remember past failures and their solutions, informing future diagnoses with historical context.
- **Webhook Security**: Implements HMAC SHA-256 signature verification for all incoming GitHub webhooks.
- **Idempotency**: Prevents duplicate comments on the same commit failure and unnecessary API requests.
- **Fully Containerized**: Environment-agnostic setup using Docker Compose.

---

## High-Level Architecture

The system is built as a distributed architecture for scalability and reliability:

1.  **Ingress (Go/Gin)**: A high-performance receiver that validates GitHub Webhook signatures and queues events into RabbitMQ.
2.  **Message Broker (RabbitMQ)**: Decouples the receiver from the analysis engine, ensuring reliable event delivery.
3.  **Analysis Engine (Python/Pika)**: The "Brain" of the operation. It fetches logs, diffs, and files, consults the LLM, and manages the RAG pipeline.
4.  **Vector Store (PostgreSQL/pgvector)**: Stores embeddings of historical failures to provide relevant context for new issues.
5.  **Docker Compose**: Orchestrates the entire stack for single-command deployment.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- A GitHub Personal Access Token (PAT) with `repo` scopes.
- A Groq API Key (or OpenAI/Anthropic).

### Quick Start
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/ai-ci-debugger.git
    cd ai-ci-debugger
    ```

2.  **Configure Environment:**
    Create a `.env` file based on `.env.example`:
    ```env
    RABBITMQ_URL=
    PORT=
    GITHUB_TOKEN=
    GITHUB_WEBHOOK_SECRET=
    GROQ_API_KEY=
    POSTGRES_USER=
    POSTGRES_PASSWORD=
    POSTGRES_DB=
    DATABASE_URL=
    ```

3.  **Launch Infrastructure:**
    ```bash
    docker compose up -d --build
    ```

4.  **Expose the Receiver:**
    Use `ngrok` or a reverse proxy to expose the port to the internet and point your GitHub Webhook (`workflow_job` events) to `https://your-domain.com/webhook`.

---

## Tech Stack

| Component | Technology |
| :--- | :--- |
| **Ingress Service** | Go (Gin) |
| **Worker Service** | Python (Pika, Sentence-Transformers) |
| **Messaging** | RabbitMQ |
| **Vector Database** | PostgreSQL + pgvector |
| **AI Model** | Llama-3.1-8b-instant (via Groq) |
| **Infrastructure** | Docker, Docker Compose |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.