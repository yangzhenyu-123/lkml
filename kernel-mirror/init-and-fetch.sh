#!/usr/bin/env bash
set -euo pipefail

# ===== 默认环境变量 =====
KERNEL_REPO="${KERNEL_REPO:-https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git}"
FETCH_INTERVAL="${FETCH_INTERVAL:-86400}"

MIRROR_DIR="/git/linux.git"

# ===== 优雅退出 =====
RUNNING=1
term_handler() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] 收到 SIGTERM 信号，正在优雅退出..."
  RUNNING=0
  # 终止可能正在运行的 git 子进程
  pkill -TERM -P $$ 2>/dev/null || true
  exit 0
}
trap term_handler SIGTERM SIGINT

# ===== 日志辅助 =====
log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

# ===== 克隆（mirror） =====
do_clone() {
  log "开始克隆镜像：${KERNEL_REPO} -> ${MIRROR_DIR}"
  log "首次 clone 耗时较长（Linux 仓库体积较大），请耐心等待..."
  if git clone --mirror "${KERNEL_REPO}" "${MIRROR_DIR}"; then
    log "克隆完成：${MIRROR_DIR}"
  else
    log "克隆失败，退出码 $?"
    return 1
  fi
}

# ===== 增量 fetch =====
do_fetch() {
  log "开始 fetch（--all --prune）：${MIRROR_DIR}"
  if (cd "${MIRROR_DIR}" && git fetch --all --prune); then
    log "fetch 完成：${MIRROR_DIR}"
  else
    log "fetch 失败，退出码 $?"
    return 1
  fi
}

# ===== 主循环 =====
log "kernel-mirror 启动"
log "KERNEL_REPO=${KERNEL_REPO}"
log "FETCH_INTERVAL=${FETCH_INTERVAL}s"
log "MIRROR_DIR=${MIRROR_DIR}"

while [ "${RUNNING}" -eq 1 ]; do
  if [ ! -d "${MIRROR_DIR}" ]; then
    log "未检测到 ${MIRROR_DIR}，执行首次 clone"
    if ! do_clone; then
      log "clone 失败，${FETCH_INTERVAL}s 后重试"
      sleep "${FETCH_INTERVAL}"
      continue
    fi
  else
    log "检测到已有镜像 ${MIRROR_DIR}，执行增量 fetch"
    if ! do_fetch; then
      log "fetch 失败，${FETCH_INTERVAL}s 后重试"
      sleep "${FETCH_INTERVAL}"
      continue
    fi
  fi

  log "下一轮 fetch 将在 ${FETCH_INTERVAL}s 后执行"
  # 使用循环以便在 sleep 期间响应 SIGTERM
  remaining="${FETCH_INTERVAL}"
  while [ "${remaining}" -gt 0 ] && [ "${RUNNING}" -eq 1 ]; do
    step=1
    if [ "${remaining}" -lt 1 ]; then
      step="${remaining}"
    fi
    sleep "${step}"
    remaining=$((remaining - step))
  done
done

log "kernel-mirror 已退出"
