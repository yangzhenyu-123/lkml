#!/usr/bin/env bash
set -euo pipefail

# ===== 默认环境变量 =====
KERNEL_REPO="${KERNEL_REPO:-https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git}"
FETCH_INTERVAL="${FETCH_INTERVAL:-86400}"
# 首次 clone 最大重试次数（大仓库易因 SSL/网络中断失败）
CLONE_MAX_RETRIES="${CLONE_MAX_RETRIES:-3}"
# 每次重试间隔（秒）
CLONE_RETRY_INTERVAL="${CLONE_RETRY_INTERVAL:-60}"
# 是否使用浅克隆（depth=1）以加速首次拉取。设为 "1" 启用，"0" 完整克隆。
# 注意：浅克隆会丢失历史，仅适合"只需最新代码"场景。kernel 分析建议完整克隆。
CLONE_SHALLOW="${CLONE_SHALLOW:-0}"

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

# ===== git 全局配置（针对大仓库优化） =====
# - http.postBuffer: 增大到 500MB，避免大包传输中断
# - core.compression: 降低 CPU 压力，加速传输
# - http.lowSpeedLimit / lowSpeedTime: 避免慢速连接被过早断开
# - safe.directory: 宿主机预克隆的卷挂载到容器后 owner 不一致，
#   git 默认拒绝操作（dubious ownership），需显式声明信任
setup_git_config() {
  git config --global http.postBuffer 524288000
  git config --global core.compression 0
  git config --global http.lowSpeedLimit 1000
  git config --global http.lowSpeedTime 300
  # 协议优化
  git config --global protocol.version 2
  # 信任挂载进来的镜像目录（owner 可能是宿主机用户，与容器 root 不一致）
  git config --global --add safe.directory "${MIRROR_DIR}"
  git config --global --add safe.directory '*'
  log "git 全局配置已设置（postBuffer=500MB, compression=0, protocol v2, safe.directory=*）"
}

# ===== 克隆（mirror，带重试） =====
do_clone() {
  log "开始克隆镜像：${KERNEL_REPO} -> ${MIRROR_DIR}"
  log "首次 clone 耗时较长（Linux 仓库体积较大），请耐心等待..."

  local clone_args=(clone --mirror)
  if [ "${CLONE_SHALLOW}" = "1" ]; then
    clone_args+=(--depth 1)
    log "启用浅克隆（depth=1）"
  fi
  clone_args+=("${KERNEL_REPO}" "${MIRROR_DIR}")

  local attempt=0
  while [ "${attempt}" -lt "${CLONE_MAX_RETRIES}" ]; do
    attempt=$((attempt + 1))
    log "克隆尝试 ${attempt}/${CLONE_MAX_RETRIES}"

    # 清理可能残留的不完整目录
    if [ -d "${MIRROR_DIR}" ]; then
      rm -rf "${MIRROR_DIR}"
    fi

    if git "${clone_args[@]}"; then
      log "克隆完成：${MIRROR_DIR}"
      return 0
    fi

    local rc=$?
    log "克隆失败（尝试 ${attempt}/${CLONE_MAX_RETRIES}），退出码 ${rc}"
    if [ "${attempt}" -lt "${CLONE_MAX_RETRIES}" ]; then
      log "${CLONE_RETRY_INTERVAL}s 后重试..."
      # 可中断的 sleep
      local slept=0
      while [ "${slept}" -lt "${CLONE_RETRY_INTERVAL}" ] && [ "${RUNNING}" -eq 1 ]; do
        sleep 1
        slept=$((slept + 1))
      done
    fi
  done

  log "克隆失败，已达最大重试次数 ${CLONE_MAX_RETRIES}"
  return 1
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
log "CLONE_MAX_RETRIES=${CLONE_MAX_RETRIES}"
log "CLONE_SHALLOW=${CLONE_SHALLOW}"
log "MIRROR_DIR=${MIRROR_DIR}"

setup_git_config

while [ "${RUNNING}" -eq 1 ]; do
  if [ ! -d "${MIRROR_DIR}" ] || [ ! -d "${MIRROR_DIR}/objects" ]; then
    log "未检测到完整镜像 ${MIRROR_DIR}，执行首次 clone"
    if ! do_clone; then
      log "clone 失败，${FETCH_INTERVAL}s 后重试"
      # 可中断的 sleep
      remaining="${FETCH_INTERVAL}"
      while [ "${remaining}" -gt 0 ] && [ "${RUNNING}" -eq 1 ]; do
        sleep 1
        remaining=$((remaining - 1))
      done
      continue
    fi
  else
    log "检测到已有镜像 ${MIRROR_DIR}，执行增量 fetch"
    if ! do_fetch; then
      log "fetch 失败，${FETCH_INTERVAL}s 后重试"
      remaining="${FETCH_INTERVAL}"
      while [ "${remaining}" -gt 0 ] && [ "${RUNNING}" -eq 1 ]; do
        sleep 1
        remaining=$((remaining - 1))
      done
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
