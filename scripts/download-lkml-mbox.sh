#!/usr/bin/env bash
# LKML 邮件归档批量下载脚本（基于 lore.kernel.org git 分片镜像）
#
# 背景：
#   lore.kernel.org 把 LKML 邮件归档按时间分片为多个 ~1GB 的 git 仓库
#   （每个 commit = 一封邮件，commit message = 邮件正文）。
#   - 旧的 HTTP mbox 接口（*.mbox）已被 Anubis 反爬保护拦截
#   - git 协议（git clone/fetch）不受影响，是官方推荐的归档方式
#
# 仓库结构：
#   https://lore.kernel.org/lkml/0   最旧分片（~1998-2007）
#   https://lore.kernel.org/lkml/1
#   ...
#   https://lore.kernel.org/lkml/N   最新分片（当月邮件）
#
# 用法：
#   ./scripts/download-lkml-mbox.sh                            # 浅克隆最新分片（当月邮件）
#   ./scripts/download-lkml-mbox.sh --all                      # 完整克隆全部分片（~13GB+）
#   ./scripts/download-lkml-mbox.sh --shards 0 1 2             # 克隆指定分片
#   ./scripts/download-lkml-mbox.sh --since 2024-01-01         # 浅克隆指定日期之后的邮件
#   ./scripts/download-lkml-mbox.sh --latest 3                 # 克隆最新 3 个分片
#   ./scripts/download-lkml-mbox.sh --probe                    # 仅探测分片数量，不下载
#
# 选项：
#   --all              克隆全部分片（约 13GB+，包含 1998 至今全部 LKML）
#   --shards N [N...]  克隆指定分片编号
#   --latest N         仅克隆最新 N 个分片（默认 N=1，即最新分片）
#   --since YYYY-MM-DD 浅克隆指定日期之后的邮件（跨分片，节省空间）
#   --depth N          浅克隆深度（与 --since 互斥）
#   --probe            仅探测分片数量
#   --mirror-dir PATH  本地镜像目录（默认 ./volumes/lkml-mirror）
#   --jobs N           并发克隆数（默认 1，git clone 单仓库已较重）
#   --shallow           强制浅克隆（depth=1，仅最新提交）
#   --fetch             已有镜像时执行增量 fetch（不克隆）
#   -h, --help          显示帮助
#
# 依赖：git, bash 4+, curl（仅用于探测）

set -uo pipefail

# ===== 默认参数 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MIRROR_DIR="${PROJECT_ROOT}/volumes/lkml-mirror"
LKML_GIT_BASE="https://lore.kernel.org/lkml"
JOBS=1
ACTION="latest"
SHARDS=()
LATEST_COUNT=1
SINCE=""
DEPTH=""
PROBE_ONLY=0
DO_FETCH=0
SHALLOW=0

# ===== 参数解析 =====
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      sed -n '2,40p' "$0"
      exit 0
      ;;
    --all)
      ACTION="all"
      shift
      ;;
    --shards)
      ACTION="shards"
      shift
      while [[ $# -gt 0 ]] && [[ "$1" != -* ]]; do
        SHARDS+=("$1")
        shift
      done
      ;;
    --latest)
      ACTION="latest"
      LATEST_COUNT="${2:-1}"
      shift 2
      ;;
    --since)
      ACTION="since"
      SINCE="$2"
      shift 2
      ;;
    --depth)
      DEPTH="$2"
      shift 2
      ;;
    --probe)
      PROBE_ONLY=1
      shift
      ;;
    --mirror-dir)
      MIRROR_DIR="$2"
      shift 2
      ;;
    --jobs)
      JOBS="$2"
      shift 2
      ;;
    --shallow)
      SHALLOW=1
      shift
      ;;
    --fetch)
      DO_FETCH=1
      shift
      ;;
    *)
      echo "未知参数: $1" >&2
      echo "使用 --help 查看帮助" >&2
      exit 1
      ;;
  esac
done

# ===== 工具函数 =====
log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

# 探测单个分片是否存在
shard_exists() {
  local shard="$1"
  local result
  result=$(timeout 15 git ls-remote "${LKML_GIT_BASE}/${shard}" 2>&1 | head -1)
  [[ "${result}" == *"HEAD"* ]]
}

# 探测最大分片编号（即最新分片）
# 分片 0 = 最旧，分片 N = 最新
probe_max_shard() {
  local max=-1
  local i=0
  # 二分查找加速
  local lo=0 hi=200
  # 先线性探测上界
  while [[ ${hi} -lt 1000 ]]; do
    if shard_exists "${hi}"; then
      lo=${hi}
      hi=$((hi * 2))
    else
      break
    fi
  done
  # 二分查找最大存在编号
  while [[ ${lo} -lt ${hi} ]]; do
    local mid=$(( (lo + hi + 1) / 2 ))
    if shard_exists "${mid}"; then
      lo=${mid}
    else
      hi=$((mid - 1))
    fi
  done
  echo "${lo}"
}

# ===== 主流程 =====
mkdir -p "${MIRROR_DIR}"

log "=========================================="
log " LKML 邮件归档批量下载（git 分片镜像）"
log "=========================================="
log " 镜像目录 : ${MIRROR_DIR}"
log " Git 源   : ${LKML_GIT_BASE}/{0..N}"
log " 模式     : ${ACTION}"
[[ "${ACTION}" == "latest" ]] && log " 最新分片数 : ${LATEST_COUNT}"
[[ "${ACTION}" == "since" ]] && log " 起始日期 : ${SINCE}"
[[ -n "${DEPTH}" ]] && log " 克隆深度 : ${DEPTH}"
[[ "${SHALLOW}" == "1" ]] && log " 强制浅克隆 : 是"
log "=========================================="

# 1. 探测分片数量
log "探测可用分片..."
MAX_SHARD=$(probe_max_shard)
TOTAL_SHARDS=$((MAX_SHARD + 1))
log "共发现 ${TOTAL_SHARDS} 个分片（编号 0-${MAX_SHARD}，0=最旧，${MAX_SHARD}=最新）"

if [[ "${PROBE_ONLY}" == "1" ]]; then
  log "仅探测模式，退出"
  exit 0
fi

# 2. 确定要克隆的分片列表
TARGET_SHARDS=()
case "${ACTION}" in
  all)
    for ((i=0; i<=MAX_SHARD; i++)); do
      TARGET_SHARDS+=("${i}")
    done
    log "将克隆全部分片（共 ${#TARGET_SHARDS[@]} 个，预计 ~$((TOTAL_SHARDS))GB+）"
    ;;
  shards)
    if [[ ${#SHARDS[@]} -eq 0 ]]; then
      echo "错误：--shards 需指定分片编号" >&2
      exit 1
    fi
    for s in "${SHARDS[@]}"; do
      if [[ "${s}" -gt "${MAX_SHARD}" ]] 2>/dev/null; then
        log "警告：分片 ${s} 超出最大值 ${MAX_SHARD}，跳过"
      else
        TARGET_SHARDS+=("${s}")
      fi
    done
    log "将克隆指定分片：${TARGET_SHARDS[*]}"
    ;;
  latest)
    if [[ ${LATEST_COUNT} -gt ${TOTAL_SHARDS} ]]; then
      LATEST_COUNT=${TOTAL_SHARDS}
    fi
    for ((i=0; i<LATEST_COUNT; i++)); do
      TARGET_SHARDS+=("$((MAX_SHARD - i))")
    done
    log "将克隆最新 ${LATEST_COUNT} 个分片：${TARGET_SHARDS[*]}"
    ;;
  since)
    # --since 模式：仅克隆可能包含该日期之后邮件的分片
    # 简化策略：克隆最新 2 个分片（最新分片通常覆盖最近 1-2 年）
    # 完整策略需逐分片检查最早 commit 日期，这里简化
    log "--since 模式：克隆最新 2 个分片并用 --shallow-since 过滤"
    TARGET_SHARDS+=("${MAX_SHARD}")
    if [[ ${MAX_SHARD} -ge 1 ]]; then
      TARGET_SHARDS+=("$((MAX_SHARD - 1))")
    fi
    ;;
esac

if [[ ${#TARGET_SHARDS[@]} -eq 0 ]]; then
  log "没有需要克隆的分片，退出"
  exit 0
fi

# 3. 构造 clone 参数
CLONE_ARGS=(clone --bare)
if [[ "${ACTION}" == "since" ]] && [[ -n "${SINCE}" ]]; then
  CLONE_ARGS+=(--shallow-since="${SINCE}")
elif [[ -n "${DEPTH}" ]]; then
  CLONE_ARGS+=(--depth "${DEPTH}")
elif [[ "${SHALLOW}" == "1" ]]; then
  CLONE_ARGS+=(--depth 1)
fi

# 4. 克隆 / fetch
clone_shard() {
  local shard="$1"
  local target_dir="${MIRROR_DIR}/lkml-${shard}.git"
  local url="${LKML_GIT_BASE}/${shard}"

  if [[ -d "${target_dir}" ]]; then
    if [[ "${DO_FETCH}" == "1" ]]; then
      log "  [fetch] 分片 ${shard}（已有镜像，增量拉取）"
      if (cd "${target_dir}" && git fetch --all --prune 2>&1); then
        log "  [完成] 分片 ${shard} fetch 完成"
        return 0
      else
        log "  [失败] 分片 ${shard} fetch 失败" >&2
        return 1
      fi
    else
      log "  [跳过] 分片 ${shard}（已存在，使用 --fetch 增量更新）"
      return 0
    fi
  fi

  log "  [clone] 分片 ${shard} -> ${target_dir}"
  log "          URL: ${url}"
  if (cd "${MIRROR_DIR}" && git "${CLONE_ARGS[@]}" "${url}" "lkml-${shard}.git" 2>&1); then
    local size
    size=$(du -sh "${target_dir}" 2>/dev/null | cut -f1)
    log "  [完成] 分片 ${shard} (${size})"
    return 0
  else
    local rc=$?
    log "  [失败] 分片 ${shard} 克隆失败（退出码 ${rc}）" >&2
    # 清理半成品
    rm -rf "${target_dir}"
    return ${rc}
  fi
}

export -f clone_shard
export MIRROR_DIR LKML_GIT_BASE DO_FETCH
export CLONE_ARGS_STR="${CLONE_ARGS[*]}"
# 注意：xargs 子进程需要重新解析 CLONE_ARGS 字符串
# 为简化，改为顺序克隆（git clone 单仓库较重，并发意义不大）

log ""
log "开始克隆，共 ${#TARGET_SHARDS[@]} 个分片..."
log ""

FAILED=()
for shard in "${TARGET_SHARDS[@]}"; do
  if ! clone_shard "${shard}"; then
    FAILED+=("${shard}")
  fi
done

# 5. 汇总
log ""
log "=========================================="
log " 完成"
log "=========================================="
log " 镜像目录：${MIRROR_DIR}"
log ""
log " 分片清单："
if ls "${MIRROR_DIR}"/lkml-*.git >/dev/null 2>&1; then
  for d in "${MIRROR_DIR}"/lkml-*.git; do
    if [[ -d "${d}" ]]; then
      shard_num=$(basename "${d}" | sed 's/lkml-\([0-9]*\)\.git/\1/')
      size=$(du -sh "${d}" 2>/dev/null | cut -f1)
      # 取最新 commit 日期作为时间范围上界
      latest_date="(未知)"
      if latest=$(cd "${d}" && git log -1 --format='%ai' 2>/dev/null | cut -d' ' -f1); then
        latest_date="${latest}"
      fi
      echo "  分片 ${shard_num}  ${size}  最新提交: ${latest_date}"
    fi
  done | sort -t' ' -k2 -n
fi
log ""
total_size=$(du -sh "${MIRROR_DIR}" 2>/dev/null | cut -f1)
log " 总大小：${total_size}"

if [[ ${#FAILED[@]} -gt 0 ]]; then
  log " 失败分片：${FAILED[*]}" >&2
  exit 1
fi

log ""
log " 说明："
log "   - 每个 commit 对应一封 LKML 邮件（commit message = 邮件正文）"
log "   - 分片 0 = 最旧（~1998），分片 N = 最新（当月）"
log "   - 增量更新：重新运行带 --fetch 参数"
log "   - backend 会自动从 ${MIRROR_DIR} 读取归档数据"
