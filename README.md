# AI CI Debugger

### *Autonomous Analysis Engine for DevOps*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go)](https://go.dev/)
[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat&logo=docker)](https://www.docker.com/)

**AI CI Debugger** An event-driven, microservices-based AI agent designed to monitor GitHub Actions, diagnose CI/CD failures using LLMs (Llama 3.1 via Groq), and post actionable fixes directly back to GitHub commits.

---

## Key Features

The system is built as a distributed architecture to ensure scalability and reliability:

- **Instant Analysis**: Automated diagnosis within seconds of job failure.
- **Deep Context**: Analysis of the **code diff** alongside the **failing logs** to understand *why* the change broke the build.
- **Actionable Fixes**: Provides specific code suggestions directly in the GitHub commit comments.
- **Webhook Security**: Implements HMAC SHA-256 signature verification for all incoming GitHub webhooks and implements idempotency.
- **Fully Containerized:** Environment-agnostic setup. If you have Docker, you can run the entire infrastructure in seconds.
- **Blindingly Fast:** Powered by Groq's Llama-3.1-8b-instant model for sub-second diagnosis generation.

---

## High-Level Architecture

The system is built as a distributed architecture to ensure scalability and reliability:

1.  **Ingress (Go/Gin)**: A high-performance receiver that validates GitHub Webhook signatures and queues events.
2.  **Message Broker (RabbitMQ)**: Ensures reliability and decoupling between the receiver and the AI engine.
3.  **Analysis Engine (Python/Pika)**: The "Brain" of the operation. It fetches logs, retrieves commit diffs, and consults the LLM.
4.  **Vector Store (PostgreSQL/pgvector)**: (In development) Enables Retrieval-Augmented Generation (RAG) to reference historical failures and documentation.
5.  **Docker Compose:** Orchestrates the entire stack into a single-command deployment.

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
    RABBITMQ_URL=your_rabbitmq_url
    PORT=your_api_port
    GITHUB_TOKEN=your_github_pat
    GITHUB_WEBHOOK_SECRET=your_webhook_secret
    GROQ_API_KEY=your_groq_key
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
| **Backend** | Go (Gin) |
| **Worker** | Python |
| **Messaging** | RabbitMQ |
| **Database** | PostgreSQL + pgvector |
| **Infrastructure** | Docker, Docker Compose |
| **AI Model** | Llama-3.1 (via Groq) |
| **Tunneling** | ngrok |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.