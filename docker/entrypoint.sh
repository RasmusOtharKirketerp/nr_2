#!/bin/sh
set -eu

MODE="${1:-web}"
shift || true

export NEWSREADER_DATA_DIR="${NEWSREADER_DATA_DIR:-/app/data}"
export NEWSREADER_VAR_DIR="${NEWSREADER_VAR_DIR:-/var/newsreader}"
export NEWSREADER_LOG_DIR="${NEWSREADER_LOG_DIR:-${NEWSREADER_VAR_DIR}/logs}"
export PYTHONPATH="${PYTHONPATH:-/app/src}"

mkdir -p "${NEWSREADER_DATA_DIR}" "${NEWSREADER_VAR_DIR}" "${NEWSREADER_LOG_DIR}"

log() {
  printf '[entrypoint] %s\n' "$*"
}

ensure_shutdown() {
  if [ "$#" -eq 0 ]; then
    return
  fi

  for pid in "$@"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
}

run_stack() {
  STACK_DAEMON_CMD="${NEWSREADER_STACK_DAEMON_CMD:-python -m newsreader.main --daemon}"
  STACK_WEB_CMD="${NEWSREADER_STACK_WEB_CMD:-python -m newsreader.main --flask}"

  log "Starting article daemon"
  sh -c "$STACK_DAEMON_CMD" &
  DAEMON_PID=$!

  log "Starting Flask web server"
  sh -c "$STACK_WEB_CMD" &
  WEB_PID=$!

  terminate() {
    log "Forwarding shutdown signal"
    ensure_shutdown "$DAEMON_PID" "$WEB_PID"
  }

  trap terminate INT TERM

  set +e
  STATUS=0
  while :; do
    if ! kill -0 "$DAEMON_PID" 2>/dev/null; then
      wait "$DAEMON_PID"
      STATUS=$?
      log "Article daemon exited with status $STATUS"
      break
    fi

    if ! kill -0 "$WEB_PID" 2>/dev/null; then
      wait "$WEB_PID"
      STATUS=$?
      log "Web server exited with status $STATUS"
      break
    fi

    sleep 1
  done

  terminate

  wait "$DAEMON_PID" 2>/dev/null || true
  wait "$WEB_PID" 2>/dev/null || true

  set -e

  exit "$STATUS"
}

cleanup_daemon_lock() {
  lock_path="${NEWSREADER_VAR_DIR}/news_daemon.pid"

  if [ ! -f "$lock_path" ]; then
    return
  fi

  pid=$(cat "$lock_path" 2>/dev/null || printf '')

  case "$pid" in
    ''|*[!0-9]*)
      log "Removing malformed daemon lock at $lock_path"
      rm -f "$lock_path"
      return
      ;;
  esac

  if [ ! -d "/proc/$pid" ]; then
    log "Removing stale daemon lock (PID $pid missing)"
    rm -f "$lock_path"
    return
  fi

  if ! tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "newsreader.main"; then
    log "Removing non-daemon lock (PID $pid)"
    rm -f "$lock_path"
  fi
}

case "$MODE" in
  web)
    exec python -m newsreader.main --flask "$@"
    ;;
  daemon)
    cleanup_daemon_lock
    exec python -m newsreader.main --daemon "$@"
    ;;
  fetch)
    exec python -m newsreader.main --fetch "$@"
    ;;
  stack|all|both)
    cleanup_daemon_lock
    run_stack
    ;;
  fetch-then-web)
    log "Running one-time article fetch..."
    python -m newsreader.main --fetch
    log "Starting Flask web server"
    exec python -m newsreader.main --flask "$@"
    ;;
  *)
    exec "$MODE" "$@"
    ;;
esac
