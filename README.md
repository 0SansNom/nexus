# 🌟 NEXUS

> **Personal Autonomous AI Assistant with Multi-Agent Architecture**

NEXUS is a highly capable, autonomous AI assistant that leverages a distributed multi-agent architecture to handle complex workflows securely and efficiently.

---

## 📑 Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Components](#components)
- [API Reference](#api-reference)
- [Development](#development)
- [Security](#security)
- [License](#license)

---

## 🎯 Overview

NEXUS acts as your personal autonomous agent system, capable of understanding high-level objectives, breaking them down into actionable plans, and executing them through specialized worker agents. All data remains local and encrypted, ensuring your privacy while providing cutting-edge AI assistance.

---

## 🏗 Architecture

NEXUS utilizes a robust layered architecture designed for modularity and scalability:

- **Coordinator (Go)**: The central brain. Handles orchestration, exposes an HTTP API/WebSocket server, manages scheduling, and interacts with the user via a clean Dashboard.
- **Agents (Python)**: Specialized workers that perform specific tasks (e.g., Email, Calendar, Memory) asynchronously.
- **Message Broker (Redis)**: Facilitates pub/sub communication and task queueing between the Coordinator and Agents.
- **Storage**:
  - **SQLite**: Local, encrypted persistent storage for objectives and state.
  - **ChromaDB**: High-performance vector database for semantic search and long-term memory.

---

## 🚀 Getting Started

### Prerequisites

- **Docker** and **Docker Compose**
- **Go 1.22+** (for local development)
- **Python 3.12+** (for local development)

### Installation & Setup

1. **Initialize the project:**
   ```bash
   make init
   ```

2. **Configure your environment:**
   Edit the `.env` file with your specific credentials:
   ```env
   # Required
   LLM_API_KEY=your-anthropic-api-key

   # Optional - Email agent configuration
   IMAP_HOST=imap.gmail.com
   EMAIL_USERNAME=your-email@gmail.com
   EMAIL_PASSWORD=your-app-password
   ```

3. **Build and start the system:**
   ```bash
   make build
   make up
   ```

4. **Access the Dashboard:**
   Open your browser and navigate to: [http://localhost:3000](http://localhost:3000)

---

## 🧩 Components

### 🧠 Coordinator
A robust Go-based core that handles:
- Exposing the HTTP API and handling real-time WebSocket connections.
- Serving the interactive Dashboard.
- Scheduling objectives via cron jobs.
- Decomposing complex plans leveraging LLMs.
- Aggregating results from all agents.

### 🤖 Agents
Independent Python processes tailored for specific domains. They:
- Listen for tasks on Redis pub/sub channels.
- Execute specialized, domain-specific actions.
- Report real-time results and activity back to the Coordinator.
- Request explicit human validation for sensitive operations.

**Available Agents:**
- 📧 **email_agent**: Handles all IMAP/SMTP email operations (reading, summarizing, answering).
- 📅 **calendar_agent**: Integrates with Google Calendar for event scheduling and management.
- 🧠 **memory_agent**: Manages vector search capabilities via ChromaDB to provide contextual awareness.

---

## 📡 API Reference

NEXUS provides a comprehensive REST API.

| Resource | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| **Objectives** | `/api/objectives` | `GET` | List all objectives |
| | `/api/objectives` | `POST` | Create a new objective |
| | `/api/objectives/:id` | `GET` | Retrieve specific objective details |
| | `/api/objectives/:id` | `PUT` | Update an existing objective |
| | `/api/objectives/:id` | `DELETE`| Delete an objective |
| | `/api/objectives/:id/execute`| `POST`| Execute an objective immediately |
| **Validations** | `/api/validations` | `GET` | List all pending human validations |
| | `/api/validations/:id/approve`| `POST`| Approve a sensitive action |
| | `/api/validations/:id/reject` | `POST`| Reject an action |
| **Activity** | `/api/activity` | `GET` | Retrieve the global activity feed |
| **Memory** | `/api/memory` | `GET` | List memory entries |
| | `/api/memory/:key` | `GET` | Retrieve a specific memory entry |
| | `/api/memory/:key` | `PUT` | Update/Set a memory entry |
| | `/api/memory/:key` | `DELETE`| Delete a memory entry |
| **WebSocket** | `/ws` | `WS` | Subscribe to real-time agent updates |

---

## 🛠 Development

### Local Development Flow

```bash
# Start infrastructure only (Redis)
docker-compose up redis -d

# Run the coordinator natively
make run-local

# Run a specific agent locally
cd agents/email_agent && python main.py
```

### Testing & Utilities

```bash
make test          # Run the test suite
make logs          # View all aggregated logs
make logs-redis    # View Redis-specific logs
make redis-cli     # Attach to Redis CLI
make status        # Show current service status
```

---

## 🔒 Security

Security is deeply ingrained into the NEXUS architecture:

- 🛡️ **Isolated Network**: All internal ports are bound strictly to `127.0.0.1`.
- 🔐 **Encrypted Storage**: Database content is secured using SQLCipher.
- 🔑 **Secret Management**: All sensitive data is injected via environment variables only.
- 👤 **Human-in-the-Loop**: Strict human validation gates for sensitive or irreversible actions.
- 📦 **Resource Hardening**: strict limits on container resources to prevent exhaustion attacks.

---

## 📄 License

This project is licensed under the **MIT License**.
