#!/bin/sh
# lib.sh — shared plumbing for hooks/orca/*-hook.sh event scripts.
#
# Design: the Claude Code event type is declared EXPLICITLY — via $1 to
# orca_hook_lib_entry, the ORCA_HOOK_EVENT env (set by the dedicated
# claude-hook-<Event>.sh scripts), or the structured "hook_event_name" JSON
# field. No payload content sniffing.
#
# Sourced, not executed. Stdin is read EXACTLY ONCE per pipeline
# (orca_hook_payload), which sets:
#   _orca_payload       raw payload ('{}' when stdin is empty)
#   _orca_payload_empty "1" when stdin was empty, else ""
#
# Event schemas emitted (Claude Code v2 hookSpecificOutput):
#   SessionStart       {"hookSpecificOutput":{"hookEventName":"SessionStart"}}
#   UserPromptSubmit   {"...","hookEventName":"UserPromptSubmit","additionalContext":""}
#   PreToolUse         {"...","hookEventName":"PreToolUse","permissionDecision":"allow"}
#   PostToolUse        {"...","hookEventName":"PostToolUse","additionalContext":""}
#   Stop               {"...","hookEventName":"Stop","additionalContext":""}

# --- payload -----------------------------------------------------------------
orca_hook_payload() {
  _orca_raw=$({ command -p cat 2>/dev/null || cat; })
  if [ -n "$_orca_raw" ]; then
    _orca_payload="$_orca_raw"
    _orca_payload_empty=""
  else
    _orca_payload='{}'
    _orca_payload_empty=1
  fi
}

# --- schema emission ---------------------------------------------------------
orca_hook_emit() {
  case "$1" in
    SessionStart)
      printf '{"hookSpecificOutput":{"hookEventName":"SessionStart"}}\n' ;;
    UserPromptSubmit)
      printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":""}}\n' ;;
    PostToolUse)
      printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":""}}\n' ;;
    Stop)
      printf '{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":""}}\n' ;;
    PreToolUse|*)
      # Unknown/missing event: fail-open allow, never block the agent.
      printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n' ;;
  esac
}

# --- JSON escaping for spool lines -------------------------------------------
orca_hook_json_escape() { printf %s "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g'; }

# --- endpoint config ----------------------------------------------------------
orca_hook_endpoint_source() {
  if [ -n "${ORCA_AGENT_HOOK_ENDPOINT:-}" ] && [ -r "$ORCA_AGENT_HOOK_ENDPOINT" ]; then
    unset ORCA_AGENT_HOOK_TRANSPORT
    . "$ORCA_AGENT_HOOK_ENDPOINT" 2>/dev/null || :
  fi
}

# --- spool (offline fallback when the Orca hook server is unreachable) --------
orca_hook_spool() {
  # $1 = event name, $2 = source label, $3 = payload
  case "$1" in PreToolUse|PostToolUse|PostToolUseFailure) return 0 ;; esac
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
      "$(orca_hook_json_escape "$1")" \
      "$(orca_hook_json_escape "${ORCA_PANE_KEY:-}")" \
      "$(orca_hook_json_escape "${ORCA_TAB_ID:-}")" \
      "$(orca_hook_json_escape "${ORCA_WORKTREE_ID:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_HOOK_ENV:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_HOOK_VERSION:-}")" \
      "$(orca_hook_json_escape "${ORCA_AGENT_LAUNCH_TOKEN:-}")" \
      "$(orca_hook_json_escape "$2")" \
      "$orca_spool_now" "$3"; } >> "$orca_spool_file" 2>/dev/null || :
  chmod 600 "$orca_spool_file" 2>/dev/null || :
}

# --- forward: form-encoded (default transport) --------------------------------
orca_hook_forward_form() {
  # $1 = event name, $2 = source label (claude|antigravity), $3 = payload
  printf '%s' "$3" | curl -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/$2" \
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
    --data-urlencode "hook_event_name=$1" \
    --data-urlencode "payload@-" >/dev/null 2>&1
}

# --- forward: raw-json-v1 transport -------------------------------------------
orca_hook_forward_raw() {
  # $1 = event name, $2 = source label, $3 = payload
  command -v base64 >/dev/null 2>&1 && command -v tr >/dev/null 2>&1 || return 1
  orca_hook_metadata=$(printf '%s\037%s\037%s\037%s\037%s\037%s' \
    "$ORCA_PANE_KEY" "$ORCA_TAB_ID" "$ORCA_AGENT_LAUNCH_TOKEN" \
    "$ORCA_WORKTREE_ID" "$ORCA_AGENT_HOOK_ENV" "$ORCA_AGENT_HOOK_VERSION" \
    | base64 | tr -d '\n') || return 1
  [ -n "$orca_hook_metadata" ] || return 1
  printf '%s' "$3" | curl -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/$2" \
    --connect-timeout "${connect_timeout:-0.5}" --max-time "${max_time:-1.5}" \
    --noproxy "127.0.0.1" \
    -H "Content-Type: application/json" \
    -H "X-Orca-Agent-Hook-Token: ${ORCA_AGENT_HOOK_TOKEN}" \
    -H "X-Orca-Agent-Hook-Meta-Encoding: base64" \
    -H "X-Orca-Agent-Hook-Meta: ${orca_hook_metadata}" \
    --data-binary @- >/dev/null 2>&1
}

# --- event resolution (explicit sources only; no stdin needed) ----------------
orca_hook_resolve() {
  # 1. $1 = explicit event name
  case "$1" in
    SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop) printf %s "$1"; return ;;
  esac
  # 2. ORCA_HOOK_EVENT env (set by the dedicated claude-hook-<Event>.sh scripts)
  case "${ORCA_HOOK_EVENT:-}" in
    SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop) printf %s "$ORCA_HOOK_EVENT"; return ;;
  esac
  # No event resolved (caller may still inspect the payload's hook_event_name).
  printf ''
}

# --- full Claude Code pipeline -------------------------------------------------
orca_hook_lib_entry() {
  _orca_event=$(orca_hook_resolve "$1")
  orca_hook_payload
  # 3. Structured hook_event_name field in the payload (antigravity-style
  #    contract) — a single well-known JSON key, not heuristic sniffing.
  if [ -z "$_orca_event" ]; then
    case "$_orca_payload" in
      *'"hook_event_name"'*)
        for _orca_candidate in $(
            printf %s "$_orca_payload" | tr ',' '\n' | tr -d '"{} ' \
              | sed -n 's/^hook_event_name:\(.*\)$/\1/p'); do
          case "$_orca_candidate" in
            SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop)
              _orca_event="$_orca_candidate" ;;
          esac
        done
        ;;
    esac
  fi
  # 4. Empty stdin => SessionStart (SessionStart hooks run without stdin).
  if [ -z "$_orca_event" ] && [ -n "$_orca_payload_empty" ]; then
    _orca_event="SessionStart"
  fi
  # 5. Nothing known => fail-open PreToolUse allow.
  orca_hook_emit "${_orca_event:-PreToolUse}"
  if [ -n "$DEVIN_PROJECT_DIR" ] || [ -n "$CLAUDE_JOB_DIR" ]; then
    exit 0
  fi
  orca_hook_endpoint_source
  if [ -z "${ORCA_AGENT_HOOK_PORT:-}" ] || [ -z "${ORCA_AGENT_HOOK_TOKEN:-}" ] || [ -z "${ORCA_PANE_KEY:-}" ]; then
    orca_hook_spool "${_orca_event:-PreToolUse}" "${ORCA_HOOK_SOURCE:-claude}" "$_orca_payload"
    exit 0
  fi
  if [ "${ORCA_AGENT_HOOK_TRANSPORT:-}" = "raw-json-v1" ]; then
    orca_hook_forward_raw "${_orca_event:-PreToolUse}" "${ORCA_HOOK_SOURCE:-claude}" "$_orca_payload" \
      || orca_hook_spool "${_orca_event:-PreToolUse}" "${ORCA_HOOK_SOURCE:-claude}" "$_orca_payload"
  else
    orca_hook_forward_form "${_orca_event:-PreToolUse}" "${ORCA_HOOK_SOURCE:-claude}" "$_orca_payload" \
      || orca_hook_spool "${_orca_event:-PreToolUse}" "${ORCA_HOOK_SOURCE:-claude}" "$_orca_payload"
  fi
  exit 0
}
