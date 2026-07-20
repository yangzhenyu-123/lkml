#!/usr/bin/env bash
# LKML mbox 批量下载脚本
#
# 用法：
#   ./scripts/download-lkml-mbox.sh                       # 下载当年所有月份
#   ./scripts/download-lkml-mbox.sh 2023                  # 下载 2023 全年
#   ./scripts/download-lkml-mbox.sh 2023 2024             # 下载 2023-2024 两年
#   ./scripts/download-lkml-mbox.sh 2023 2024 2025        # 下载指定多个年份
#   ./scripts/download-lkml-mbox.sh 2023 2023 --current   # 强制仅 2023 全年（含未来月份会跳过）
#
# 特性：
#   - 断点续传（wget -c / curl -C -）
#   - 自动跳过未来月份（不存在的月份会 404，脚本会捕获并跳过）
#   - 当前月份默认会重新下载覆盖（增量刷新），用 --skip-current 跳过
#   - 下载到 ./volumes/lkml-mbox/（与 docker-compose 挂载路径一致）
#   - 支持并行下载（--jobs N，默认 4）
#
# 依赖：wget 或 curl（任选其一），bash 4+

set -uo pipefail

# ===== 默认参数 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MBOX_DIR="${PROJECT_ROOT}/volumes/lkml-mbox"
LKML_BASE="${LKML_BASE_URL:-https://lore.kernel.org/linux-kernel}"
JOBS=4
SKIP_CURRENT=0
CURRENT_YEAR=$(date -u +%Y)
CURRENT_MONTH=$(date -u +%m)

# ===== 参数解析 =====
YEARS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    --jobs)
      JOBS="$2"
      shift 2
      ;;
    --skip-current)
      SKIP_CURRENT=1
      shift
      ;;
    --current)
      # 仅处理当前年
      YEARS=("$CURRENT_YEAR")
      shift
      ;;
    --dir)
      MBOX_DIR="$2"
      shift 2
      ;;
    *)
      YEARS+=("$1")
      shift
      ;;
  esac
done

# 默认：当年
if [[ ${#YEARS[@]} -eq 0 ]]; then
  YEARS=("$CURRENT_YEAR")
fi

# ===== 下载工具选择 =====
if command -v wget >/dev/null 2>&1; then
  DL_TOOL="wget"
elif command -v curl >/dev/null 2>&1; then
  DL_TOOL="curl"
else
  echo "错误：需要 wget 或 curl，请先安装。" >&2
  exit 1
fi

mkdir -p "${MBOX_DIR}"
echo "=========================================="
echo " LKML mbox 批量下载"
echo "=========================================="
echo " 下载目录 : ${MBOX_DIR}"
echo " 下载源   : ${LKML_BASE}"
echo " 年份     : ${YEARS[*]}"
echo " 并发数   : ${JOBS}"
echo " 下载工具 : ${DL_TOOL}"
echo " 当前日期 : ${CURRENT_YEAR}-${CURRENT_MONTH} (UTC)"
echo "=========================================="

# ===== 单个月份下载函数 =====
download_month() {
  local year="$1"
  local month="$2"
  local fname="${year}-${month}.mbox"
  local url="${LKML_BASE}/${fname}"
  local target="${MBOX_DIR}/${fname}"

  # 跳过未来月份
  if [[ "${year}" -gt "${CURRENT_YEAR}" ]] || \
     ([[ "${year}" -eq "${CURRENT_YEAR}" ]] && [[ "${month}" -gt "${CURRENT_MONTH}" ]]); then
    echo "  [跳过] ${fname} (未来月份)"
    return 0
  fi

  # 当前月份处理
  local is_current=0
  if [[ "${year}" -eq "${CURRENT_YEAR}" ]] && [[ "${month}" -eq "${CURRENT_MONTH}" ]]; then
    is_current=1
    if [[ "${SKIP_CURRENT}" -eq 1 ]]; then
      echo "  [跳过] ${fname} (当前月份，--skip-current)"
      return 0
    fi
    # 当前月份：删除旧文件后重新下载（增量刷新）
    if [[ -f "${target}" ]]; then
      echo "  [刷新] ${fname} (当前月份，删除旧文件重新下载)"
      rm -f "${target}"
    fi
  fi

  # 检查是否已下载（非当前月份且文件存在则跳过）
  if [[ "${is_current}" -eq 0 ]] && [[ -f "${target}" ]] && [[ -s "${target}" ]]; then
    local size
    size=$(stat -c%s "${target}" 2>/dev/null || stat -f%z "${target}" 2>/dev/null || echo 0)
    echo "  [存在] ${fname} ($(numfmt --to=iec ${size} 2>/dev/null || echo "${size}B"))"
    return 0
  fi

  # 下载
  echo "  [下载] ${fname} ..."
  local rc=0
  if [[ "${DL_TOOL}" == "wget" ]]; then
    wget -q -c -O "${target}.part" "${url}" 2>&1 || rc=$?
  else
    curl -sL -C - -o "${target}.part" "${url}" 2>&1 || rc=$?
  fi

  # 检查结果（404 表示该月份尚无归档）
  if [[ ${rc} -ne 0 ]]; then
    rm -f "${target}.part"
    if [[ "${is_current}" -eq 0 ]] && [[ "${month}" -ge "${CURRENT_MONTH}" ]] && \
       [[ "${year}" -ge "${CURRENT_YEAR}" ]]; then
      echo "  [无归档] ${fname} (该月份尚未发布，跳过)"
      return 0
    fi
    echo "  [失败] ${fname} (退出码 ${rc})" >&2
    return ${rc}
  fi

  # 检查文件是否为空或 HTML 错误页
  if [[ ! -s "${target}.part" ]]; then
    rm -f "${target}.part"
    echo "  [空文件] ${fname} (可能是未来月份或尚未发布)"
    return 0
  fi

  # 检查是否为 HTML 错误页（mbox 应以 "From " 开头）
  local first_line
  first_line=$(head -c 100 "${target}.part" 2>/dev/null | head -1)
  if [[ "${first_line}" != "From "* ]] && [[ "${first_line}" != "<"* ]]; then
    # 不像 mbox，可能是错误响应
    if [[ "${first_line}" == "<html"* ]] || [[ "${first_line}" == "<!DOCTYPE"* ]]; then
      rm -f "${target}.part"
      echo "  [无归档] ${fname} (服务器返回 HTML 错误页)"
      return 0
    fi
  fi

  mv "${target}.part" "${target}"
  local size
  size=$(stat -c%s "${target}" 2>/dev/null || stat -f%z "${target}" 2>/dev/null || echo 0)
  echo "  [完成] ${fname} ($(numfmt --to=iec ${size} 2>/dev/null || echo "${size}B"))"
}

export -f download_month
export MBOX_DIR LKML_BASE CURRENT_YEAR CURRENT_MONTH SKIP_CURRENT DL_TOOL

# ===== 生成下载任务列表 =====
TASKS=()
for year in "${YEARS[@]}"; do
  for month in 01 02 03 04 05 06 07 08 09 10 11 12; do
    TASKS+=("${year} ${month}")
  done
done

echo ""
echo "开始下载，共 ${#TASKS[@]} 个月份任务..."
echo ""

# ===== 并行下载 =====
# 使用 xargs 并行执行
printf '%s\n' "${TASKS[@]}" | xargs -P "${JOBS}" -I {} bash -c '
  read year month <<< "{}"
  download_month "${year}" "${month}"
'

echo ""
echo "=========================================="
echo " 下载完成"
echo "=========================================="
echo " 文件位于：${MBOX_DIR}"
echo ""
echo " 文件清单："
ls -lh "${MBOX_DIR}"/*.mbox 2>/dev/null | awk '{printf "  %s  %s\n", $5, $9}' || echo "  (无 .mbox 文件)"
echo ""
total_size=$(du -sh "${MBOX_DIR}" 2>/dev/null | cut -f1)
echo " 总大小：${total_size}"
echo ""
echo " 下一步：启动容器后，kernel-mirror 与 backend 会自动使用这些文件"
echo "        当月文件会由 Celery beat 每天 03:00 UTC 增量刷新"
