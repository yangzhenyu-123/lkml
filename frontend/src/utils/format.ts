// 工具函数：时间格式化、状态颜色映射、文本截断

import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import type { ItemStatus, JobStatus } from "@/types";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

export function formatDateTime(s: string | null): string {
  if (!s) return "—";
  return dayjs(s).format("YYYY-MM-DD HH:mm");
}

export function formatDate(s: string | null): string {
  if (!s) return "—";
  return dayjs(s).format("YYYY-MM-DD");
}

export function fromNow(s: string | null): string {
  if (!s) return "—";
  return dayjs(s).fromNow();
}

export function truncate(s: string | null, n = 60): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

// 任务状态 → 颜色 + 文本
export const jobStatusMap: Record<JobStatus, { color: string; text: string }> = {
  pending: { color: "default", text: "待开始" },
  running: { color: "processing", text: "运行中" },
  stage1: { color: "blue", text: "阶段1 候选查找" },
  stage2: { color: "purple", text: "阶段2 上游对照" },
  stage3: { color: "gold", text: "阶段3 优化方案" },
  stage4: { color: "green", text: "阶段4 专利提取" },
  completed: { color: "success", text: "已完成" },
  failed: { color: "error", text: "失败" },
};

// 条目状态 → 颜色 + 文本
export const itemStatusMap: Record<ItemStatus, { color: string; text: string }> = {
  pending: { color: "default", text: "待处理" },
  running: { color: "processing", text: "运行中" },
  success: { color: "success", text: "成功" },
  failed: { color: "error", text: "失败" },
  retrying: { color: "warning", text: "重试中" },
};

// 阶段元信息
export const stageMeta = [
  {
    no: 1 as const,
    name: "候选查找",
    color: "stage-s1",
    desc: "扫描 LKML，过滤性能优化类 PATCH 邮件",
    retryable: false,
    icon: "🔍",
  },
  {
    no: 2 as const,
    name: "上游对照+分类",
    color: "stage-s2",
    desc: "git patch-id 匹配，标记未合入，按子系统分类",
    retryable: false,
    icon: "⚖️",
  },
  {
    no: 3 as const,
    name: "优化方案",
    color: "stage-s3",
    desc: "调用 OpenCode 生成改进方案",
    retryable: true,
    icon: "⚡",
  },
  {
    no: 4 as const,
    name: "专利提取",
    color: "stage-s4",
    desc: "调用 patent-disclosure-skill 产出交底书",
    retryable: true,
    icon: "📜",
  },
];

// 字节数 → 人类可读
export function humanSize(bytes: number): string {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}
