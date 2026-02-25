# RESUME.md — GenAI MLOps Stack

## Current State (v0.5 — cleanup + git init)

### Git
- Initialized on `main` branch, initial commit `8edb2be`
- 16 files tracked, `.gitignore` carves out `n8n-data/workflows/` from the `n8n-data/*` ignore
- No remote configured yet

### Active Workflows (4)
| ID | Endpoint | Purpose |
|----|----------|---------|
| `ollama-webhook-v1` | `POST /webhook/ollama` | Direct Ollama passthrough |
| `prompt-ollama-v1` | `POST /webhook/prompt-ollama` | Prompt-driven Ollama with registry lookup |
| `prompt-crud-v1` | `POST /webhook/prompts` | Prompt registry CRUD (create/get/list/update/delete) |
| `prompt-eval-v1` | `POST /webhook/eval` | Prompt evaluation → MLflow experiment tracking |

### Cleanup Done This Session
- Deleted stale `test-code-v1` debugging workflow from n8n (no JSON file, direct DB delete)
- Initialized git repo, branch `main`, initial commit with all 16 project files
- Updated `.gitignore` to track `n8n-data/workflows/` while ignoring rest of `n8n-data/`

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

## Verified Working
- All 4 webhooks responding
- MLflow experiments: `assistant-eval` (6 runs), `summarizer-eval` (1 run)
- `task import-workflow` imports and activates all 4 workflows
- Host→MLflow API queries work after allowed-hosts fix
- `task dev` / `task stop` lifecycle clean

## Next Steps
- [local] Test `task nuke && task dev` for full bootstrap from scratch
- Add error handling workflow (separate n8n error trigger workflow)
- Add prompt A/B testing (multiple aliases: `production`, `canary`)
- Add comparative eval (run same test cases across 2 prompt versions, compare metrics)
- Consider n8n API key setup for programmatic workflow management
- Consider batch prompt operations (import/export multiple prompts)
- Create GitHub remote and push
