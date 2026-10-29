/** Pure helper used by launcher contract tests. Actual wrappers implement this same child-only policy. */
export function createClaudeChildEnvironment(parentEnv, { gatewayBaseUrl, gatewayApiKey = "" }) {
  const child = { ...parentEnv };
  // Never let provider credentials/configuration enter the Claude Code process by inheritance.
  for (const key of [
    "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_MODEL",
    "OPENAI_COMPATIBLE_MODEL_MAP", "OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH",
    "OPENAI_COMPATIBLE_CAPABILITIES", "OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP",
    "GATEWAY_API_KEY", "GATEWAY_CONFIG_FILE", "GATEWAY_ENV_FILE"
  ]) delete child[key];
  child.ANTHROPIC_BASE_URL = gatewayBaseUrl;
  child.CLAUDE_CODE_AUTO_MODE_SERVER = "0";
  // The bridge reshapes system/content fields and cannot preserve Anthropic-only reasoning/beta semantics.
  child.CLAUDE_CODE_ATTRIBUTION_HEADER = "0";
  child.CLAUDE_CODE_DISABLE_THINKING = "1";
  if (!child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS) child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1";
  if (!child.CLAUDE_CODE_EFFORT_LEVEL) child.CLAUDE_CODE_EFFORT_LEVEL = "auto";
  // Use only the local gateway token. Clearing an inherited API key avoids sending a provider key to localhost.
  delete child.ANTHROPIC_API_KEY;
  if (gatewayApiKey) child.ANTHROPIC_AUTH_TOKEN = gatewayApiKey;
  else delete child.ANTHROPIC_AUTH_TOKEN;
  return child;
}
