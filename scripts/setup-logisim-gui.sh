#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}/tinycpu-logisim-gui-${UID}"
DISPLAY_NUMBER="${TINYCPU_DISPLAY:-:99}"
VNC_PORT="${TINYCPU_VNC_PORT:-5900}"
JAR="${LOGISIM_JAR:-$ROOT/.venv/Include/logisim-evolution-4.1.0-all.jar}"
PROJECT="$ROOT/hardware/logisim/TinyCPU.circ"

usage() {
  cat <<'EOF'
Usage: ./gui.sh COMMAND

Prepare a visible, manually operated Logisim desktop on Ubuntu/Debian.

Commands:
  install  Install Java, Xvfb, Fluxbox, x11vnc and diagnostic X11 tools.
  check    Check the installed programs and the pinned Logisim JAR.
  start    Start a private virtual desktop and VNC server on localhost.
  run      Open TinyCPU.circ on that desktop (close Logisim to return).
  status   Show the configured display, VNC endpoint and process state.
  stop     Stop the VNC server, window manager and virtual display.

The VNC server listens only on localhost and has no password. Reach it through
an SSH tunnel, for example: ssh -L 5900:localhost:5900 USER@HOST
Then connect a local VNC viewer to localhost:5900. A virtual desktop that is
not viewed and manually operated does not satisfy the AP 20.8 GUI check.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

pid_file() {
  printf '%s/%s.pid\n' "$STATE_DIR" "$1"
}

is_running() {
  local file pid
  file="$(pid_file "$1")"
  [[ -f "$file" ]] || return 1
  read -r pid < "$file"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

require_command() {
  command -v "$1" >/dev/null 2>&1 ||
    die "'$1' is missing; run '$0 install' first"
}

install_packages() {
  command -v apt-get >/dev/null 2>&1 ||
    die "automatic installation supports Ubuntu/Debian with apt-get only"

  local -a elevate=()
  if (( EUID != 0 )); then
    command -v sudo >/dev/null 2>&1 ||
      die "run this command as root or install sudo"
    elevate=(sudo)
  fi

  export DEBIAN_FRONTEND=noninteractive
  "${elevate[@]}" apt-get update
  "${elevate[@]}" apt-get install -y --no-install-recommends \
    openjdk-21-jre \
    xvfb \
    fluxbox \
    x11vnc \
    x11-utils \
    xauth \
    xdotool

  printf '\nInstallation complete. Next run:\n  %s check\n  %s start\n' "$0" "$0"
}

check_dependencies() {
  local failed=0 command_name
  for command_name in java Xvfb fluxbox x11vnc xdpyinfo xauth xdotool; do
    if command -v "$command_name" >/dev/null 2>&1; then
      printf 'ok:      %-10s %s\n' "$command_name" "$(command -v "$command_name")"
    else
      printf 'missing: %s\n' "$command_name" >&2
      failed=1
    fi
  done

  if [[ -f "$JAR" ]]; then
    printf 'ok:      Logisim JAR %s\n' "$JAR"
  else
    printf 'missing: Logisim JAR %s\n' "$JAR" >&2
    failed=1
  fi
  [[ -f "$PROJECT" ]] || {
    printf 'missing: project %s\n' "$PROJECT" >&2
    failed=1
  }

  (( failed == 0 )) || return 1
  java -version
}

start_process() {
  local name="$1"
  shift
  nohup "$@" >"$STATE_DIR/$name.log" 2>&1 &
  printf '%s\n' "$!" > "$(pid_file "$name")"
}

start_desktop() {
  require_command Xvfb
  require_command fluxbox
  require_command x11vnc
  require_command xdpyinfo
  mkdir -p "$STATE_DIR"

  if ! is_running xvfb; then
    start_process xvfb Xvfb "$DISPLAY_NUMBER" -screen 0 1600x1000x24 -nolisten tcp
  fi

  local ready=0
  for _ in {1..50}; do
    if DISPLAY="$DISPLAY_NUMBER" xdpyinfo >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.1
  done
  (( ready == 1 )) || die "Xvfb did not start; see $STATE_DIR/xvfb.log"

  if ! is_running fluxbox; then
    start_process fluxbox env DISPLAY="$DISPLAY_NUMBER" fluxbox
  fi
  if ! is_running x11vnc; then
    start_process x11vnc x11vnc \
      -display "$DISPLAY_NUMBER" \
      -rfbport "$VNC_PORT" \
      -localhost \
      -forever \
      -shared \
      -nopw
  fi

  sleep 0.5
  is_running x11vnc || die "x11vnc did not start; see $STATE_DIR/x11vnc.log"
  printf 'Virtual desktop started on DISPLAY=%s.\n' "$DISPLAY_NUMBER"
  printf 'VNC listens on localhost:%s only.\n' "$VNC_PORT"
  printf 'Open an SSH tunnel, connect a VNC viewer, then run:\n  %s run\n' "$0"
}

run_logisim() {
  require_command java
  require_command xdpyinfo
  [[ -f "$JAR" ]] || die "Logisim JAR not found: $JAR"
  [[ -f "$PROJECT" ]] || die "TinyCPU project not found: $PROJECT"
  DISPLAY="$DISPLAY_NUMBER" xdpyinfo >/dev/null 2>&1 ||
    die "no X server on $DISPLAY_NUMBER; run '$0 start' first"
  printf 'Opening %s on DISPLAY=%s ...\n' "$PROJECT" "$DISPLAY_NUMBER"
  DISPLAY="$DISPLAY_NUMBER" java -jar "$JAR" "$PROJECT"
}

show_status() {
  printf 'DISPLAY=%s\nVNC=localhost:%s\nSTATE_DIR=%s\n' \
    "$DISPLAY_NUMBER" "$VNC_PORT" "$STATE_DIR"
  local name
  for name in xvfb fluxbox x11vnc; do
    if is_running "$name"; then
      printf '%-7s running (PID %s)\n' "$name" "$(<"$(pid_file "$name")")"
    else
      printf '%-7s stopped\n' "$name"
    fi
  done
}

stop_desktop() {
  local name file pid
  for name in x11vnc fluxbox xvfb; do
    file="$(pid_file "$name")"
    if [[ -f "$file" ]]; then
      read -r pid < "$file"
      if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
      fi
      rm -f "$file"
    fi
  done
  printf 'TinyCPU virtual desktop stopped.\n'
}

case "${1:-}" in
  install) install_packages ;;
  check) check_dependencies ;;
  start) start_desktop ;;
  run) run_logisim ;;
  status) show_status ;;
  stop) stop_desktop ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
