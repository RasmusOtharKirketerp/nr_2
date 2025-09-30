#!/bin/sh
set -eu

MODE="${1:-web}"
shift || true

export NEWSREADER_DATA_DIR="${NEWSREADER_DATA_DIR:-/app/data}"
export NEWSREADER_VAR_DIR="${NEWSREADER_VAR_DIR:-/var/newsreader}"
export NEWSREADER_LOG_DIR="${NEWSREADER_LOG_DIR:-${NEWSREADER_VAR_DIR}/logs}"
export PYTHONPATH="${PYTHONPATH:-/app/src}"

mkdir -p "${NEWSREADER_DATA_DIR}" "${NEWSREADER_VAR_DIR}" "${NEWSREADER_LOG_DIR}"

case "$MODE" in
  web)
    exec python -m newsreader.main --flask "$@"
    ;;
  daemon)
    exec python -m newsreader.main --daemon "$@"
    ;;
  fetch)
    exec python -m newsreader.main --fetch "$@"
    ;;
  *)
    exec "$MODE" "$@"
    ;;
esac
