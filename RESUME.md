# RESUME.md — GenAI MLOps Stack

## What Was Built

### Prompt Evaluation Workflow (v0.4)
- **n8n workflow**: `n8n-data/workflows/prompt-eval.json` — 3-node workflow:
  Webhook → Eval Handler (Code/axios) → Respond
- **Endpoint**: `POST /webhook/eval`
- Runs prompt against test cases, logs results to MLflow experiment tracking
- Each test case: fetch prompt → render → call Ollama → measure latency → log to MLflow run
- Auto-creates experiment per prompt (`{prompt_name}-eval`)

### Eval API Reference
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

Response includes per-test results (response, latency_ms, tokens, run_id) + summary (avg_latency, avg_tokens).

### MLflow REST API Endpoints Used
- `/experiments/get-by-name` + `/experiments/create` — get-or-create experiment
- `/runs/create` — start a run
- `/runs/log-batch` — log params + metrics + tags in single call
- `/runs/update` — set status to FINISHED

### Key Discovery: DNS Rebinding with Port
- MLflow `--allowed-hosts` needs `localhost:5050` (with port), not just `localhost`
- curl sends `Host: localhost:5050` when hitting `http://localhost:5050`
- Updated docker-compose to include both `localhost` and `localhost:5050`
- `docker compose restart` does NOT re-read compose file — must use `docker compose up -d` to recreate

### Key Discovery: Shell Variable Expansion in Workflow Generation
- `python3 -c "..."` with double quotes causes shell to expand `$input` to empty string
- Must use heredoc (`python3 << 'PYEOF'`) to preserve `$input` in n8n Code node references
- Always verify `$input` presence in generated JSON before importing

## What Broke and Why
- **`$input` eaten by shell**: `python3 -c "...$input..."` expanded `$input` to empty. Fixed with heredoc.
- **DNS rebinding from host**: `localhost:5050` not in allowed-hosts (only `localhost` without port). Fixed by adding `localhost:5050`.
- **`docker compose restart` stale config**: Restart reuses existing container config. Must `docker compose up -d` to pick up compose changes.

## Verified Working
- `task import-workflow` — imports and activates all 4 workflows
- `POST /webhook/eval` with `assistant` prompt — 3 runs logged to `assistant-eval` experiment
- `POST /webhook/eval` with `summarizer` prompt — 1 run logged to `summarizer-eval` experiment
- MLflow UI shows experiments with runs, params (prompt_name, version, model, label), metrics (latency_ms, token counts)
- Host→MLflow API queries work after allowed-hosts fix
- All previous workflows still working (ollama, prompt-ollama, prompts CRUD)

## Previous Session Work (Preserved)
- Prompt CRUD workflow (`prompt-crud.json`) — 5 actions via single webhook
- Prompt-driven workflow (`prompt-ollama.json`) — 5-node workflow
- Seed script (`scripts/seed_prompts.py`) — seeds assistant + summarizer prompts
- MLflow `--allowed-hosts` fix for DNS rebinding protection
- n8n Code Node constraints (VM2 sandbox, no fetch, use axios)

## Next Steps
- [local] Test `task nuke && task dev` for full bootstrap from scratch
- Add error handling workflow (separate n8n error trigger workflow)
- Add prompt A/B testing (multiple aliases: `production`, `canary`)
- Add comparative eval (run same test cases across 2 prompt versions, compare metrics)
- Consider n8n API key setup for programmatic workflow management
- Consider batch prompt operations (import/export multiple prompts)
