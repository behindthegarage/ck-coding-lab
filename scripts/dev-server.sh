#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="ck-coding-lab-local.service"
PROJECT_DIR="/home/openclaw/ck-coding-lab-local"
UNIT_SRC="$PROJECT_DIR/ck-coding-lab-local.service"
UNIT_DST="$HOME/.config/systemd/user/$SERVICE_NAME"
PORT="5006"

usage() {
  cat <<'EOF'
Usage: scripts/dev-server.sh <command>

Commands:
  install   Install/update the user service unit and reload systemd
  start     Start the local dev server service
  stop      Stop the local dev server service
  restart   Restart the local dev server service
  status    Show service + port status
  logs      Tail recent service logs
EOF
}

require_systemd_user() {
  if ! systemctl --user --version >/dev/null 2>&1; then
    echo "systemctl --user is not available on this machine." >&2
    exit 1
  fi
}

install_unit() {
  require_systemd_user
  mkdir -p "$(dirname "$UNIT_DST")"
  install -m 644 "$UNIT_SRC" "$UNIT_DST"
  systemctl --user daemon-reload
  echo "Installed $SERVICE_NAME to $UNIT_DST"
}

port_report() {
  ss -ltnp "sport = :$PORT" 2>/dev/null || true
}

ensure_port_free_for_start() {
  if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    return 0
  fi

  if port_report | awk 'NR>1 {exit 0} END {exit 1}'; then
    echo "Port $PORT is already in use by a non-service process:" >&2
    port_report >&2
    echo "Stop that process or run: scripts/dev-server.sh restart (if this service owns it)." >&2
    exit 1
  fi
}

start_service() {
  install_unit
  ensure_port_free_for_start
  systemctl --user start "$SERVICE_NAME"
  sleep 1
  status_service
}

stop_service() {
  require_systemd_user
  systemctl --user stop "$SERVICE_NAME"
  status_service
}

restart_service() {
  install_unit
  systemctl --user restart "$SERVICE_NAME"
  sleep 1
  status_service
}

status_service() {
  require_systemd_user
  echo "=== systemd ==="
  systemctl --user --no-pager --full status "$SERVICE_NAME" || true
  echo
  echo "=== port $PORT ==="
  port_report
}

logs_service() {
  require_systemd_user
  journalctl --user -u "$SERVICE_NAME" -n 50 -f
}

cmd="${1:-}"
case "$cmd" in
  install) install_unit ;;
  start) start_service ;;
  stop) stop_service ;;
  restart) restart_service ;;
  status) status_service ;;
  logs) logs_service ;;
  *) usage; exit 1 ;;
esac
