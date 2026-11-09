#!/usr/bin/env bash
# 一次性启动 Chapter-14 的四个服务
# - 任一服务退出时，提示并打印该服务最后 10 行日志
# - Ctrl+C 一次性关闭所有服务
# - 日志写入 logs/ 目录，可随时 tail -f 查看
set -u
cd "$(dirname "$0")"

# macOS 上 gunicorn fork 出的 worker 会触发 ObjC fork 安全检查而崩溃，必须禁用
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

NAMES=(planning execution memory summarization)
CMDS=(
  "python -m planning.run --config config/planning.yml --run.port 10000"
  "python -m execution.run --config-path config/execution.yml --port 15000"
  "python -m memory.session.run --config config/session_memory.yml --port 20000"
  "python -m summarization.run --config config/summarizaztion.yml --port 25000"
)
PORTS=(10000 15000 20000 25000)

# 启动前检查端口占用，避免之前踩过的“双实例共享端口”问题
for i in "${!NAMES[@]}"; do
  if lsof -nP -iTCP:"${PORTS[$i]}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "错误: 端口 ${PORTS[$i]} 已被占用（${NAMES[$i]} 可能已在运行）。"
    echo "先用 lsof -nP -iTCP:${PORTS[$i]} -sTCP:LISTEN 找到进程并停止后重试。"
    exit 1
  fi
done

PIDS=()
cleanup() {
  echo ""
  echo "[start_services] 正在停止所有服务..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
  echo "[start_services] 已全部退出。"
  exit 0
}
trap cleanup SIGINT SIGTERM

for i in "${!NAMES[@]}"; do
  name="${NAMES[$i]}"
  ${CMDS[$i]} > "$LOG_DIR/$name.log" 2>&1 &
  pid=$!
  PIDS+=("$pid")
  echo "[start_services] $name 已启动 (pid $pid, 端口 ${PORTS[$i]}, 日志 $LOG_DIR/$name.log)"
done

echo ""
echo "[start_services] 全部启动完成。Ctrl+C 关闭所有服务。"
echo ""

# 监控循环：发现服务退出立即提示
while true; do
  sleep 2
  for i in "${!NAMES[@]}"; do
    pid="${PIDS[$i]:-}"
    [ -z "$pid" ] && continue
    if ! kill -0 "$pid" 2>/dev/null; then
      echo ""
      echo "================================================================"
      echo "⚠️  服务 [${NAMES[$i]}] 已退出 (pid $pid)，最后 10 行日志:"
      tail -n 10 "$LOG_DIR/${NAMES[$i]}.log"
      echo "================================================================"
      unset "PIDS[$i]"
      if [ "${#PIDS[@]}" -eq 0 ]; then
        echo "[start_services] 所有服务都已退出，脚本结束。"
        exit 1
      fi
    fi
  done
done
