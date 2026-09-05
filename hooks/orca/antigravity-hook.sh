#!/bin/sh
# Orca hook — antigravity runtime.
#
# Contract: the runtime passes the event via the ORCA_ANTIGRAVITY_EVENT env.
# Emits the v2 schema (PreToolUse => "ask" for antigravity), forwards the
# payload to the Orca hook server (spool fallback when offline).
#
# Uses the shared hooks/orca/lib.sh; keeps its own entry so the
# antigravity-specific ORCA_ANTIGRAVITY_EVENT variable and the "ask" decision
# stay local to this runtime.
payload=$({ command -p cat 2>/dev/null || cat; })
[ -n "$payload" ] || payload='{}'

_event=""
case "${ORCA_ANTIGRAVITY_EVENT:-}" in
  Stop)
    printf '{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":""}}\n' ;;
  PreToolUse)
    # Antigravity PreToolUse: surface an "ask" decision (runtime-specific).
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask"}}\n' ;;
  *)
    # Unknown/missing: fail-open allow.
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n' ;;
esac

orca_hook_json_escape() { printf %s "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g'; }

orca_hook_spool() {
  case "${ORCA_ANTIGRAVITY_EVENT:-}" in PreToolUse|PostToolUse|PostToolUseFailure) return 0 ;; esac
  [ -n "${ORCA_AGENT_HOOK_ENDPOINT:-}" ] || return 0
  [ -n "${ORCA_PANE_KEY:-}" ] || return 0
  [ -r "$ORCA_AGENT_HOOK_ENDPOINT" ] || return 0
  orca_spool_base=${ORCA_AGENT_HOOK_ENDPOINT%/*}
  orca_spool_dir="$orca_spool_base/spool"
  mkdir -p "$orca_spool_dir" 2>/dev/null || return 0
  chmod 700 "$orca_spool_dir" 2>/dev/null || :
  orca_spool_id=$(printf %s "${ORCA_PANE_KEY:-unknown}" | tail -c 36 | tr '/:' '__')
  orca_spool_file="$orca_spool_dir/pane-$orca_spool_id.jsonl"
  if [ -f "$orca_spool_file" ] && find "$orca_spool_file" -mtime +7 -print -quit 2>/dev/null | grep -q .; then : > "$orca_spool_file"; fi
  [ -f "$orca_spool_file" ] || : > "$orca_spool_file"
  orca_spool_size=$(wc -c < "$orca_spool_file" 2>/dev/null || printf 0)
  [ "$orca_spool_size" -lt 5242880 ] || return 0
  orca_spool_now=$(date +%s 2>/dev/null || printf 0)
  orca_spool_now=$((orca_spool_now * 1000))
  { printf '\n{"hookEventName":"%s","paneKey":"%s","tabId":"%s","worktreeId":"%s","env":"%s","version":"%s","launchToken":"%s","source":"%s","receivedAt":%s,"payload":%s}\n' \
      "$(orca_hook_json_escape "${ORCA_ANTIGRAVITY_EVENT:-}")" \
      "$(orca_hook_json_escape "${ORCA_PANE_KEY:-}")" \
      "$(orca_hook_json_escape "${ORCA_TAB_ID:-}")" \
      "$(orca_hook_json_escape "${ORCA_WORKTREE_ID:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_HOOK_ENV:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_HOOK_VERSION:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_LAUNCH_TOKEN:-}")" \
      "$(orca_hook_json_escape "antigravity")" \
      "$orca_spool_now" "$payload"; } >> "$orca_spool_file" 2>/dev/null || :
  chmod 600 "$orca_spool_file" 2>/dev/null || :
}

orca_hook_endpoint_source() {
  if [ -n "${ORCA_AGENT_HOOK_ENDPOINT:-}" ] && [ -r "$ORCA_AGENT_HOOK_ENDPOINT" ]; then
    unset ORCA_AGENT_HOOK_TRANSPORT
    . "$ORCA_AGENT_HOOK_ENDPOINT" 2>/dev/null || :
  fi
}

orca_hook_forward() {
  if [ -z "${ORCA_AGENT_HOOK_PORT:-}" ] || [ -z "${ORCA_AGENT_HOOK_TOKEN:-}" ] || [ -z "${ORCA_PANE_KEY:-}" ]; then
    orca_hook_spool
    return 0
  fi
  if [ "${ORCA_AGENT_HOOK_TRANSPORT:-}" = "raw-json-v1" ] && command -v base64 >/dev/null 2>&1 && command -v tr >/dev/null 2>&1; then
    orca_hook_metadata=$(printf '%s\037%s\037%s\037%s\037%s\037%s' \
      "$ORCA_PANE_KEY" "$ORCA_TAB_ID" "$ORCA_AGENT_LAUNCH_TOKEN" \
      "$ORCA_WORKTREE_ID" "$ORCA_AGENT_HOOK_ENV" "$ORCA_AGENT_HOOK_VERSION" \
      | base64 | tr -d '\n') &&
      [ -n "$orca_hook_metadata" ] &&
      printf '%s' "$payload" | curl -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/antigravity" \
        --connect-timeout "${connect_timeout:-0.5}" --max-time "${max_time:-1.5}" \
        --noproxy "127.0.0.1" \
        -H "Content-Type: application/json" \
        -H "X-Orca-Agent-Hook-Token: ${ORCA_AGENT_HOOK_TOKEN}" \
        -H "X-Orca-Agent-Hook-Meta-Encoding: base64" \
        -H "X-Orca-Agent-Hook-Meta: ${orca_hook_metadata}" \
        --data-binary @- >/dev/null 2>&1 || orca_hook_spool
  else
    printf '%s' "$payload" | curl -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/antigravity" \
      --connect-timeout "${connect_timeout:-0.5}" --max-time "${max_time:-1.5}" \
      --noproxy "127.0.0.1" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -H "X-Orca-Agent-Hook-Token: ${ORCA_AGENT_HOOK_TOKEN}" \
      --data-urlencode "paneKey=${ORCA_PANE_KEY}" \
      --data-urlencode "tabId=${ORCA_TAB_ID}" \
      --data-urlencode "launchToken=${ORCA_AGENT_LAUNCH_TOKEN}" \
      --data-urlencode "worktreeId=${ORCA_WORKTREE_ID}" \
      --data-urlencode "env=${ORCA_AGENT_HOOK_ENV}" \
      --data-urlencode "version=${ORCA_AGENT_HOOK_VERSION}" \
      --data-urlencode "hook_event_name=${ORCA_ANTIGRAVITY_EVENT}" \
      --data-urlencode "payload@-" >/dev/null 2>&1 || orca_hook_spool
  fi
}

orca_hook_endpoint_source
orca_hook_forward
exit 0
