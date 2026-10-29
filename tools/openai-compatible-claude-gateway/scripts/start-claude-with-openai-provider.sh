#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
HOST=${GATEWAY_HOST:-127.0.0.1}
ENV_FILE=${GATEWAY_ENV_FILE:-$ROOT_DIR/.env}
read_env_file_value() {
  [ -f "$ENV_FILE" ] || return 0
  awk -v key="$1" '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    {
      line=$0
      sub(/^[[:space:]]*export[[:space:]]+/, "", line)
      split(line, pair, "=")
      if (pair[1] != key) next
      sub(/^[^=]*=/, "", line)
      sub(/^[[:space:]]+/, "", line); sub(/[[:space:]]+$/, "", line)
      if (substr(line,1,1)=="\"" && substr(line,length(line),1)=="\"") line=substr(line,2,length(line)-2)
      else if (substr(line,1,1)=="\047" && substr(line,length(line),1)=="\047") line=substr(line,2,length(line)-2)
      else sub(/[[:space:]]+#.*/, "", line)
      print line; exit
    }
  ' "$ENV_FILE"
}
if [ -n "${GATEWAY_PORT:-}" ]; then PORT=$GATEWAY_PORT; else PORT=$(read_env_file_value GATEWAY_PORT); fi
PORT=${PORT:-3456}
if [ -n "${GATEWAY_HOST:-}" ]; then HOST=$GATEWAY_HOST; else HOST=$(read_env_file_value GATEWAY_HOST); fi
HOST=${HOST:-127.0.0.1}
if [ -n "${GATEWAY_API_KEY:-}" ]; then LOCAL_TOKEN=$GATEWAY_API_KEY; else LOCAL_TOKEN=$(read_env_file_value GATEWAY_API_KEY); fi
if [ -n "${GATEWAY_BASE_URL:-}" ]; then BASE_URL=${GATEWAY_BASE_URL%/}; else
  case "$HOST" in
    localhost|127.*) BASE_HOST=$HOST ;;
    ::1|\[::1\]) BASE_HOST='[::1]' ;;
    *) BASE_HOST=127.0.0.1 ;;
  esac
  BASE_URL="http://$BASE_HOST:$PORT"
fi
CLAUDE_BIN=${CLAUDE_BIN:-claude}
DISABLE_EXPERIMENTAL_BETAS=${CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS:-1}
EFFORT_LEVEL=${CLAUDE_CODE_EFFORT_LEVEL:-auto}

case "$HOST" in
  127.*|localhost|::1|\[::1\]) ;;
  *) printf '%s\n' "Warning: GATEWAY_HOST is not obviously loopback; ensure the server has explicit remote-bind opt-in and local gateway authentication." >&2 ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  printf '%s\n' "curl is required for the gateway health check." >&2
  exit 2
fi
if ! curl --noproxy '*' --fail --silent --show-error --max-time 2 "$BASE_URL/health" >/dev/null; then
  printf '%s\n' "Gateway health check failed at $BASE_URL/health. Start it in a separate terminal: cd '$ROOT_DIR' && npm start" >&2
  exit 1
fi
if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1 && [ ! -x "$CLAUDE_BIN" ]; then
  printf '%s\n' "Claude Code executable was not found. Set CLAUDE_BIN to its path or ensure 'claude' is on PATH." >&2
  exit 127
fi

# env creates a child-only environment: caller variables and shell profiles remain unchanged.
if [ -n "$LOCAL_TOKEN" ]; then
  exec env \
    -u OPENAI_COMPATIBLE_API_KEY -u OPENAI_COMPATIBLE_BASE_URL -u OPENAI_COMPATIBLE_MODEL \
    -u OPENAI_COMPATIBLE_MAX_TOKENS_FIELD -u OPENAI_COMPATIBLE_MODEL_PASSTHROUGH \
    -u OPENAI_COMPATIBLE_MODEL_MAP -u OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH \
    -u OPENAI_COMPATIBLE_CAPABILITIES -u OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP \
    -u GATEWAY_API_KEY -u ANTHROPIC_API_KEY \
    ANTHROPIC_AUTH_TOKEN="$LOCAL_TOKEN" ANTHROPIC_BASE_URL="$BASE_URL" \
    CLAUDE_CODE_AUTO_MODE_SERVER=0 CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
    CLAUDE_CODE_DISABLE_THINKING=1 CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="$DISABLE_EXPERIMENTAL_BETAS" \
    CLAUDE_CODE_EFFORT_LEVEL="$EFFORT_LEVEL" "$CLAUDE_BIN" "$@"
else
  exec env \
    -u OPENAI_COMPATIBLE_API_KEY -u OPENAI_COMPATIBLE_BASE_URL -u OPENAI_COMPATIBLE_MODEL \
    -u OPENAI_COMPATIBLE_MAX_TOKENS_FIELD -u OPENAI_COMPATIBLE_MODEL_PASSTHROUGH \
    -u OPENAI_COMPATIBLE_MODEL_MAP -u OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH \
    -u OPENAI_COMPATIBLE_CAPABILITIES -u OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP \
    -u GATEWAY_API_KEY -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
    ANTHROPIC_BASE_URL="$BASE_URL" CLAUDE_CODE_AUTO_MODE_SERVER=0 CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
    CLAUDE_CODE_DISABLE_THINKING=1 CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="$DISABLE_EXPERIMENTAL_BETAS" \
    CLAUDE_CODE_EFFORT_LEVEL="$EFFORT_LEVEL" "$CLAUDE_BIN" "$@"
fi
