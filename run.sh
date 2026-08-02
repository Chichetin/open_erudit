#!/usr/bin/env bash
# Запуск сервера.
#
#   ./run.sh              только LAN: uvicorn на 0.0.0.0:8000
#   ./run.sh --tunnel     плюс cloudflared, публичный https-адрес
#
# На этой машине поднят полнотуннельный VPN с policy-routing, поэтому проброс
# порта с роутера не работает — ответные пакеты уходят в туннель. У Cloudflare
# Tunnel этой проблемы нет: соединение исходящее.

set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
TUNNEL=0
UVICORN_PID=""
CLOUDFLARED_PID=""
TUNNEL_LOG=""

for arg in "$@"; do
  case "$arg" in
    --tunnel) TUNNEL=1 ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Неизвестный аргумент: $arg" >&2
      exit 2
      ;;
  esac
done

cleanup() {
  [[ -n "$CLOUDFLARED_PID" ]] && kill "$CLOUDFLARED_PID" 2>/dev/null || true
  [[ -n "$UVICORN_PID" ]] && kill "$UVICORN_PID" 2>/dev/null || true
  [[ -n "$TUNNEL_LOG" ]] && rm -f "$TUNNEL_LOG" || true
}
trap cleanup EXIT INT TERM

cd "$(dirname "$0")"

uv run uvicorn app.main:app --host "$HOST" --port "$PORT" --proxy-headers &
UVICORN_PID=$!

# ждём, пока сервер начнёт отвечать
for _ in $(seq 1 50); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

# Адрес в локальной сети. Мосты докера и интерфейс VPN пропускаем: по ним
# соперник из LAN всё равно не достучится.
lan_address() {
  ip -4 -o addr show scope global 2>/dev/null \
    | grep -vE '\s(docker[0-9]*|br-[0-9a-f]+|veth[^ ]*|tun[0-9]*|wg[0-9]*)\s' \
    | awk '{print $4}' | cut -d/ -f1 | head -1
}

LAN_IP="$(lan_address || true)"
BASE_URL="http://${LAN_IP:-127.0.0.1}:${PORT}"

if [[ "$TUNNEL" -eq 1 ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared не найден. Установите: sudo pacman -S cloudflared" >&2
    exit 1
  fi

  TUNNEL_LOG="$(mktemp)"
  echo "Поднимаем туннель Cloudflare…"

  # Регистрация быстрого туннеля срывается по мелочам — таймаут запроса,
  # AAAA-запись при мёртвом IPv6 — поэтому несколько попыток.
  PUBLIC_URL=""
  for attempt in 1 2 3; do
    : >"$TUNNEL_LOG"
    cloudflared tunnel --url "http://localhost:${PORT}" >"$TUNNEL_LOG" 2>&1 &
    CLOUDFLARED_PID=$!

    for _ in $(seq 1 100); do
      # api.trycloudflare.com — адрес регистрации, он мелькает в сообщениях
      # об ошибках; нужен именно выданный хост
      PUBLIC_URL="$(grep -aom1 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" \
        | grep -v '^https://api\.' || true)"
      [[ -n "$PUBLIC_URL" ]] && break
      kill -0 "$CLOUDFLARED_PID" 2>/dev/null || break
      sleep 0.3
    done

    [[ -n "$PUBLIC_URL" ]] && break
    echo "  попытка ${attempt}: не получилось, пробуем снова" >&2
    kill "$CLOUDFLARED_PID" 2>/dev/null || true
    wait "$CLOUDFLARED_PID" 2>/dev/null || true
    CLOUDFLARED_PID=""
  done

  if [[ -z "$PUBLIC_URL" ]]; then
    echo "Адрес туннеля так и не появился. Вывод cloudflared:" >&2
    cat "$TUNNEL_LOG" >&2
    exit 1
  fi

  # Адрес выдан — но это ещё не значит, что соединения с edge встали.
  for _ in $(seq 1 40); do
    grep -aq 'Registered tunnel connection' "$TUNNEL_LOG" && break
    sleep 0.5
  done
  if ! grep -aq 'Registered tunnel connection' "$TUNNEL_LOG"; then
    echo "Туннель зарегистрирован, но соединения с Cloudflare не встали." >&2
    echo "Обычно это блокировка исходящего порта 7844 (VPN, файрвол)." >&2
    grep -aE 'ERR ' "$TUNNEL_LOG" | tail -3 >&2
    exit 1
  fi

  BASE_URL="$PUBLIC_URL"
fi

echo
echo "Сервер: ${BASE_URL}"
echo "Откройте этот адрес, нажмите «Создать партию» и отправьте сопернику вторую ссылку."
echo "Остановить — Ctrl+C."
echo

wait "$UVICORN_PID"
