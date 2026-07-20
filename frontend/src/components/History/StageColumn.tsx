import { Progress } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import ItemCard from "./ItemCard";
import { STAGE_COLORS, STAGE_COLOR_SOFT } from "./stageColors";
import { stageMeta } from "@/utils/format";
import type { JobItem, StageRecord } from "@/types";

interface Props {
  stage: StageRecord | undefined;
  items: JobItem[];
  showArrow: boolean;
  onItemClick: (item: JobItem) => void;
  onRetry: (item: JobItem) => void;
  onViewOutput: (item: JobItem) => void;
}

const STAGE_STATUS_TEXT: Record<StageRecord["status"], string> = {
  pending: "待开始",
  running: "进行中",
  completed: "已完成",
  failed: "失败",
};

export default function StageColumn({
  stage,
  items,
  showArrow,
  onItemClick,
  onRetry,
  onViewOutput,
}: Props) {
  const stageNo = (stage?.stage_no ?? 1) as 1 | 2 | 3 | 4;
  const meta = stageMeta[stageNo - 1];
  const accent = STAGE_COLORS[stageNo];
  const soft = STAGE_COLOR_SOFT[stageNo];
  const success = stage?.success_items ?? 0;
  const total = stage?.total_items ?? 0;
  const percent = total > 0 ? Math.round((success / total) * 100) : 0;
  const statusText = stage ? STAGE_STATUS_TEXT[stage.status] : "待开始";
  const showProgress = stage?.status === "running" || percent > 0;

  return (
    <div className="relative">
      <div
        className="rounded-lg bg-white shadow-card overflow-hidden"
        style={{ border: `1px solid ${accent}40` }}
      >
        {/* 头部 */}
        <div
          className="px-3 py-2.5 border-b"
          style={{ borderColor: `${accent}30`, background: `${soft}55` }}
        >
          <div className="flex items-center gap-2">
            <span className="text-xl">{meta.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="font-display font-semibold text-sm text-ink-900 truncate">
                阶段{meta.no} {meta.name}
              </div>
              <div className="text-xs text-ink-500">
                {statusText}
                {total > 0 && (
                  <span className="ml-1 font-medium" style={{ color: accent }}>
                    {success}/{total}
                  </span>
                )}
                {stage?.status === "running" && total > 0 && (
                  <span className="ml-1 text-ink-400">
                    · 失败 {stage.failed_items}
                  </span>
                )}
              </div>
            </div>
          </div>
          {showProgress && (
            <Progress
              percent={percent}
              showInfo={false}
              size="small"
              strokeColor={accent}
              className="!mt-2 !mb-0"
            />
          )}
        </div>

        {/* Items */}
        <div
          className="p-2 space-y-2 overflow-y-auto"
          style={{ maxHeight: 600 }}
        >
          {items.length === 0 ? (
            <div className="text-xs text-ink-400 text-center py-6">暂无条目</div>
          ) : (
            items.map((it) => (
              <ItemCard
                key={it.id}
                item={it}
                retryable={meta.retryable}
                onClick={() => onItemClick(it)}
                onRetry={() => onRetry(it)}
                onViewOutput={() => onViewOutput(it)}
              />
            ))
          )}
        </div>
      </div>

      {showArrow && (
        <ArrowRightOutlined
          className="hidden md:block absolute top-1/2 -right-3 -translate-y-1/2 z-10 bg-paper px-1"
          style={{ color: "#8A9FC0" }}
        />
      )}
    </div>
  );
}
