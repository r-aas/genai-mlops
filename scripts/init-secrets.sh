#!/usr/bin/env bash
# Generate Docker secrets for local development.
# Usage: ./scripts/init-secrets.sh [--force]
# Idempotent — skips existing secrets unless --force is passed.

set -euo pipefail

SECRETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/secrets"
FORCE="${1:-}"

mkdir -p "$SECRETS_DIR"

write_secret() {
    local name="$1"
    local value="$2"
    if [ -f "$SECRETS_DIR/$name" ] && [ "$FORCE" != "--force" ]; then
        echo "  ✓ $name (exists, skipping)"
        return
    fi
    printf '%s' "$value" > "$SECRETS_DIR/$name"
    chmod 600 "$SECRETS_DIR/$name"
    echo "  → $name (created)"
}

gen_password() {
    head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32
}

echo "Initializing Docker secrets in $SECRETS_DIR ..."

write_secret "n8n_postgres_password"    "$(gen_password)"
write_secret "mlflow_postgres_password" "$(gen_password)"
write_secret "minio_root_password"      "$(gen_password)"
write_secret "n8n_encryption_key"       "$(gen_password)"

echo ""
echo "Done. Secrets stored in $SECRETS_DIR/"
echo "These are gitignored and should never be committed."
