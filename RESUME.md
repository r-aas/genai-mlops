# RESUME.md — GenAI MLOps Stack

## Current State (v0.7 — Provider-agnostic inference)

### Git
- Branch `main`, remote `origin` → https://github.com/r-aas/genai-mlops (public)
- `.gitignore` carves out `n8n-data/workflows/` from the `n8n-data/*` ignore

### Active Workflows (5)
| ID | Endpoint | Purpose |
|----|----------|---------|
| `ollama-webhook-v1` | `POST /webhook/ollama` | Direct inference passthrough |
| `prompt-ollama-v1` | `POST /webhook/prompt-ollama` | Prompt-driven inference with registry lookup |
| `prompt-crud-v1` | `POST /webhook/prompts` | Prompt registry CRUD (create/get/list/update/delete) |
| `prompt-eval-v1` | `POST /webhook/eval` | Prompt evaluation → MLflow experiment tracking |
| `openai-compat-v1` | `GET/POST /webhook/v1/*` | OpenAI-compatible API (models + chat completions) |

### Provider Abstraction (v0.7)
All 4 inference workflows now use env vars instead of hardcoded Ollama URLs:

| Env Var | Default | Purpose |
|---------|---------|---------|
| `INFERENCE_BASE_URL` | `http://host.docker.internal:11434/v1` | OpenAI-compatible inference endpoint |
| `INFERENCE_DEFAULT_MODEL` | `qwen2.5:14b` | Fallback model when none specified |
| `INFERENCE_ALLOWED_MODELS` | `qwen2.5:14b,...` (7 models) | Comma-separated allowlist for public API |

- n8n expression fields use `$env.INFERENCE_BASE_URL`
- n8n Code nodes use `process.env.INFERENCE_BASE_URL`
- All have hardcoded fallback defaults so stack works without .env
- Taskfile `doctor` now checks `/v1/models` (OpenAI-compatible) instead of `/api/tags` (Ollama-specific)

### OpenAI-Compatible API
Gateway that exposes the entire stack as an OpenAI drop-in replacement:
- `GET /webhook/v1/models` — lists MLflow prompts (`owned_by: genai-mlops`) + allowed models (`owned_by: ollama`)
- `POST /webhook/v1/chat/completions` — routes by model name:
  - If model matches an MLflow prompt → prompt-enhanced path (template + inference)
  - Otherwise → direct inference pass-through (must be in allowlist)
  - Supports both `stream: true` (SSE) and `stream: false` (JSON)
  - `system_fingerprint` reveals path taken: `fp_{prompt}_v{version}` or `fp_ollama`

Usage with OpenAI SDK:
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:5678/webhook/v1", api_key="n8n")
r = client.chat.completions.create(model="assistant", messages=[{"role": "user", "content": "Hello"}])
```

## Eval API Reference
```
POST /webhook/eval
{
  "prompt_name": "assistant",
  "test_cases": [
    {"variables": {"message": "What is 2+2?"}, "label": "math"},
    {"variables": {"message": "Translate hello"}, "label": "translation"}
  ],
  "alias": "production",       // optional
  "model": "qwen2.5:14b",     // optional
  "temperature": 0.7,          // optional
  "experiment_name": "my-eval" // optional, default: {prompt_name}-eval
}
```

Response: per-test results (response, latency_ms, tokens, run_id) + summary (avg_latency, avg_tokens).

## Key Discoveries (Preserved)
- **DNS rebinding with port**: MLflow `--allowed-hosts` needs `localhost:5050` (with port), not just `localhost`
- **Shell variable expansion**: `python3 -c "..."` eats `$input`; use heredoc `<< 'PYEOF'` instead
- **`docker compose restart` vs `up -d`**: `restart` reuses existing config; `up -d` recreates with updated compose
- **n8n Code Node**: VM2 sandbox, no `fetch`, must use `require('axios')`
- **n8n CLI delete**: No `delete:workflow` command; must delete via Postgres directly
- **n8n CLI import needs secrets**: `docker exec` can't access DB secrets; must use `docker compose run --rm n8n-import`
- **prompt-ollama empty 200**: Returns 200 with empty body for non-existent prompts; callers must validate response body
- **n8n env var access**: Expression fields use `$env.VAR`, Code nodes use `process.env.VAR`
- **Workflow JSON editing**: Don't edit escaped JS in JSON by hand; regenerate via Python `json.dump()`

## Verified Working
- All 5 webhooks responding
- Provider abstraction: all workflows use `INFERENCE_*` env vars with fallback defaults
- OpenAI SDK drop-in works for both prompt-enhanced and raw models
- Model allowlist: 7 curated SFW models, enforced on both listing and execution
- MLflow experiments: `assistant-eval` (6 runs), `summarizer-eval` (1 run)
- `task import-workflow` imports and activates all 5 workflows
- `task doctor` checks OpenAI-compatible `/v1/models` endpoint
- Host→MLflow API queries work after allowed-hosts fix
- `task dev` / `task stop` lifecycle clean

## Next Steps
- [local] Test `task nuke && task dev` for full bootstrap from scratch
- Add error handling workflow (separate n8n error trigger workflow)
- Add prompt A/B testing (multiple aliases: `production`, `canary`)
- Add comparative eval (run same test cases across 2 prompt versions, compare metrics)
- Consider n8n API key setup for programmatic workflow management
- Consider batch prompt operations (import/export multiple prompts)
- Fix prompt-ollama to return 404/error for non-existent prompts instead of empty 200
