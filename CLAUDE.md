# CLAUDE.md — GenAI MLOps Stack

## Project Overview

A Docker Compose-based local MLOps platform combining **n8n** (workflow automation) and **MLflow** (experiment tracking & model registry). Designed as a lean foundation for building AI/ML workflows with a local-first philosophy.

**Local LLM**: Ollama running on bare metal (never containerized — Apple Silicon GPU constraint). Containers reach it via `host.docker.internal:11434`.

## Architecture

```
User → n8n (workflow builder) → Ollama (via host.docker.internal)
                              → MLflow (experiment tracking)
                              → External APIs

MLflow:
  backend store   → mlflow-postgres (PostgreSQL 16.8)
  artifact store  → MinIO (S3-compatible)

n8n:
  metadata store  → n8n-postgres (PostgreSQL 16.8)
  encryption key  → Docker secret
```

## Services & Ports

| Service         | Port | Purpose                              |
|-----------------|------|--------------------------------------|
| n8n             | 5678 | Workflow automation UI               |
| MLflow          | 5050 | Experiment tracking, model registry  |
| MinIO API       | 9000 | S3-compatible artifact storage       |
| MinIO Console   | 9001 | MinIO web UI                         |

Internal-only (no host ports): n8n-postgres, mlflow-postgres.

## Directory Structure

```
genai-mlops/
├── CLAUDE.md               ← you are here
├── docker-compose.yml      ← 6 services (2x PG, MinIO, bucket init, MLflow, n8n)
├── Taskfile.yml            ← task runner (task <name>)
├── .env                    ← environment config (gitignored)
├── .env.example            ← env contract (committed)
├── pyproject.toml          ← uv project for host-side tooling
├── mlflow/
│   └── Dockerfile          ← thin image: mlflow + psycopg2 + boto3
├── scripts/
│   └── init-secrets.sh     ← generates secrets/ (idempotent)
└── secrets/                ← Docker secrets (gitignored, never committed)
```

## Key Conventions

### Secrets
- All passwords are Docker secrets (file-based), never in .env or environment vars.
- Run `task init-secrets` to generate. Run `task reset-secrets` to regenerate.
- 4 secrets: `n8n_postgres_password`, `mlflow_postgres_password`, `minio_root_password`, `n8n_encryption_key`.

### Databases
- **Separate PostgreSQL instances** for n8n and MLflow (isolation over shared DB).
- Both pinned to PG 16.8 (PG 18+ has mount path breaking changes).

### Ollama / LLM
- Ollama runs natively on the Mac host — never in Docker (GPU constraint).
- All AI clients use OpenAI-compatible env vars pointing at Ollama.
- Containers use `host.docker.internal:11434` to reach Ollama.
- Standard env: `OPENAI_BASE_URL`, `OPENAI_API_KEY=ollama`, `OPENAI_MODEL=qwen2.5:14b`.

### MLflow Prompt Registry
- Prompts are managed in MLflow's Prompt Registry (v3+). Each prompt is a registered model tagged `mlflow.prompt.is_prompt=true`, template stored in `mlflow.prompt.text` tag.
- Seed prompts: `task seed-prompts` (idempotent, runs `scripts/seed_prompts.py`).
- Prompts accessed via standard MLflow REST API — no dedicated prompt endpoints needed:
  - Get by alias: `GET /api/2.0/mlflow/model-versions/get-by-alias?name=<name>&alias=production`
  - Search prompts: `GET /api/2.0/mlflow/registered-models/search?filter=tag."mlflow.prompt.is_prompt"='true'`
- n8n fetches prompts from MLflow at `http://mlflow:5050` (internal network).

### n8n Workflows
Four webhook workflows:
1. **Ollama Webhook** (`POST /webhook/ollama`) — direct message → Ollama. Payload: `{"message": "...", "model": "qwen2.5:14b"}`
2. **Prompt-Driven Ollama** (`POST /webhook/prompt-ollama`) — fetches prompt from MLflow, renders template variables, calls Ollama. Payload: `{"prompt_name": "assistant", "variables": {"message": "..."}, "model": "qwen2.5:14b"}`
3. **Prompt Registry CRUD** (`POST /webhook/prompts`) — create/read/update/delete prompts in MLflow. Actions:
   - `{"action":"create","name":"X","template":"...","commit_message":"...","tags":{"k":"v"}}` — creates prompt with production alias
   - `{"action":"get","name":"X","alias":"production"}` — returns template, variables, version, tags
   - `{"action":"list"}` — lists all prompts with aliases and tags
   - `{"action":"update","name":"X","template":"...","commit_message":"..."}` — creates new version, moves production alias
   - `{"action":"delete","name":"X"}` — deletes entire prompt (or `"version":"N"` for specific version)
4. **Prompt Evaluation** (`POST /webhook/eval`) — runs prompt against test cases, logs results to MLflow experiments. Payload:
   ```json
   {"prompt_name": "assistant", "test_cases": [{"variables": {"message": "..."}, "label": "test-1"}]}
   ```
   Optional fields: `alias` (default: production), `model`, `temperature`, `experiment_name` (default: `{prompt_name}-eval`).
   Each test case creates an MLflow run with: params (prompt_name, version, model, input, label), metrics (latency_ms, token counts), tags (label, response in mlflow.note.content).
   Results viewable in MLflow UI under the auto-created experiment.

Workflow JSON files live in `n8n-data/workflows/`. Imported on first `task dev` via n8n-import init container.

### n8n Code Node Constraints
- The Code node runs in a VM2 sandbox — `fetch` is NOT available
- Use `require('axios')` or `require('node-fetch')` for HTTP calls
- `require('http')` and `require('https')` are also available

### Task Runner
- Use `task` (Taskfile.yml) for all operations. Key tasks: `dev`, `stop`, `health`, `doctor`, `logs`, `ps`.
- Never use justfiles.

### Python
- Use `uv` for all Python operations. Never pip, venv, or poetry.

### Docker
- Single `docker-compose.yml`, no overrides.
- MLflow uses a thin custom Dockerfile (bakes in drivers, no runtime pip install).
- n8n uses the official `n8nio/n8n` image directly.
- All persistent services have `restart: unless-stopped`.

### MinIO
- Pinned to `RELEASE.2025-10-15` — final public release before minio/minio was archived.
- Auto-creates the MLflow bucket on first start via `create-bucket` init container.

## Quick Start

```bash
task setup     # sync deps, create .env, generate secrets
task dev       # start everything (builds images)
task health    # verify services are healthy
task doctor    # full environment check (Docker, Ollama, secrets)
```

## Troubleshooting

- **MLflow DNS rebinding protection**: MLflow v3 blocks requests where the Host header doesn't match allowed hosts. The `--allowed-hosts` flag in docker-compose.yml includes `mlflow:5050` so n8n (and other containers) can reach MLflow by service name.
- **Port 5000 conflict**: macOS AirPlay Receiver squats on 5000. MLflow uses 5050 to avoid this.
- **Ollama unreachable from containers**: Ensure `OLLAMA_HOST=0.0.0.0:11434` in your shell rc. Default Ollama only binds 127.0.0.1.
- **PG auth failures after secret regeneration**: Volumes store old passwords. Run `task nuke` then `task dev` for a clean start.
