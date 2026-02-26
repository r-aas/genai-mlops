# RESUME.md — GenAI MLOps Stack

## Current State (v0.9 — Production hardening)

### Git
- Branch `main`, remote `origin` → https://github.com/r-aas/genai-mlops (public)
- `.gitignore` carves out `n8n-data/workflows/` from the `n8n-data/*` ignore

### Active Workflows (3)
| ID | Endpoint | Purpose |
|----|----------|---------|
| `openai-compat-v1` | `GET/POST /webhook/v1/*` | OpenAI-compatible API (models + chat + embeddings) |
| `prompt-crud-v1` | `POST /webhook/prompts` | Prompt registry CRUD (create/get/list/update/delete) |
| `prompt-eval-v1` | `POST /webhook/eval` | Prompt evaluation → MLflow experiment tracking |

### Provider Abstraction
All inference workflows use env vars instead of hardcoded URLs:

| Env Var | Default | Purpose |
|---------|---------|---------|
| `INFERENCE_BASE_URL` | `http://host.docker.internal:11434/v1` | OpenAI-compatible inference endpoint |
| `INFERENCE_DEFAULT_MODEL` | `qwen2.5:14b` | Fallback model when none specified |
| `INFERENCE_ALLOWED_MODELS` | `qwen2.5:14b,...` (7 models) | Comma-separated allowlist for public API |

### OpenAI-Compatible API
Gateway that exposes the entire stack as an OpenAI drop-in replacement:
- `GET /webhook/v1/models` — lists MLflow prompts (`owned_by: genai-mlops`) + allowed models (`owned_by: ollama`)
- `POST /webhook/v1/chat/completions` — routes by model name:
  - If model matches an MLflow prompt → prompt-enhanced path (template rendering + inference)
  - Otherwise → direct inference pass-through (must be in allowlist)
  - Supports optional `variables` field for multi-variable template expansion
  - `system_fingerprint` reveals path taken: `fp_{prompt}_v{version}` or `fp_inference`
- `POST /webhook/v1/embeddings` — proxies to inference provider's embeddings endpoint
  - Default model: `nomic-embed-text:latest` (768 dimensions)
  - Must be in allowlist

### Error Handling (v0.9)
All endpoints return proper HTTP status codes and OpenAI-shaped error bodies:
- Chat completions: `{"error": {"message": "...", "type": "...", "param": null, "code": "..."}}` with 400/404/500
- Embeddings: same shape
- CRUD: `{"error": true, "message": "..."}` with 400/404
- Eval: `{"error": true, "message": "..."}` with 400/404
- Production alias delete guard: cannot delete version that is the current production alias

### Alias→Version Lookup (v0.9 fix)
All workflows use `/model-versions/get` API to fetch specific versions by alias, instead of relying on `latest_versions` array (which only returns the most recent version per stage and breaks when production alias points to an older version).

Usage with OpenAI SDK:
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:5678/webhook/v1", api_key="n8n")
r = client.chat.completions.create(model="assistant", messages=[{"role": "user", "content": "Hello"}])
e = client.embeddings.create(model="nomic-embed-text:latest", input="Hello")
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
  "temperature": 0.7,          // optional (0 is valid, not coerced)
  "experiment_name": "my-eval" // optional, default: {prompt_name}-eval
}
```

## Key Discoveries (Preserved)
- **DNS rebinding with port**: MLflow `--allowed-hosts` needs `localhost:5050` (with port), not just `localhost`
- **Shell variable expansion**: `python3 -c "..."` eats `$input`; use heredoc `<< 'PYEOF'` instead
- **`docker compose restart` vs `up -d`**: `restart` reuses existing config; `up -d` recreates with updated compose
- **n8n Code Node**: VM2 sandbox, no `fetch`, must use `require('axios')`
- **n8n CLI delete**: No `delete:workflow` command; must delete via Postgres directly
- **n8n CLI import needs secrets**: `docker exec` can't access DB secrets; must use `docker compose run --rm n8n-import`
- **n8n env var access**: Expression fields use `$env.VAR`, Code nodes use `process.env.VAR`
- **Workflow JSON editing**: Don't edit escaped JS in JSON by hand; regenerate via Python `json.dump()`
- **MLflow prompt search**: `registered-models/search` doesn't return prompts by default; must filter with `tags.\`mlflow.prompt.is_prompt\` = 'true'`
- **MLflow latest_versions unreliable**: Only returns latest version per stage — use `model-versions/get` with explicit version number for alias lookups
- **n8n respondToWebhook status codes**: Use typeVersion 1.2 with `options.responseCode` expression for dynamic HTTP status

## Verified Working
- All endpoints responding with proper HTTP status codes
- `/v1/embeddings` endpoint with nomic-embed-text (768 dims)
- OpenAI-shaped error responses on chat and embeddings endpoints
- Alias→version lookup works when production points to non-latest version
- Production alias delete guard prevents deleting live versions
- `temperature: 0` correctly passed through (not coerced to 0.7)
- Prompt template variable expansion with `variables` field
- `task import-workflow` imports and activates all 3 workflows
- `task dev` / `task stop` lifecycle clean

## Next Steps
- Integration tests (pytest suite hitting live stack)
- README.md for external consumers
- Real streaming (currently fakes SSE — returns full response at once)
- Prompt A/B testing (multiple aliases: `production`, `canary`)
- Comparative eval (run same test cases across 2 prompt versions, compare metrics)
