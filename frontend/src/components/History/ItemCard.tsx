import { Button, Tag, Tooltip } from "antd";
import { EyeOutlined, ReloadOutlined } from "@ant-design/icons";
import { ItemStatusBadge } from "@/components/StatusBadge";
import { truncate } from "@/utils/format";
import { STAGE_COLORS } from "./stageColors";
import type { JobItem } from "@/types";

interface Props {
  item: JobItem;
  retryable: boolean;
  onClick: () => void;
  onRetry: () => void;
  onViewOutput: () => void;
}

export default function ItemCard({ item, retryable, onClick, onRetry, onViewOutput }: Props) {
  const isFailed = item.status === "failed";
  const isSuccess = item.status === "success";
  const canRetry = retryable && (isFailed || isSuccess);
  const showViewOutput = isSuccess && (item.stage_no === 3 || item.stage_no === 4);
  const accent = STAGE_COLORS[item.stage_no];

  return (
    <div
      onClick={onClick}
      className="block p-2.5 rounded-md border bg-white cursor-pointer transition-all hover:shadow-cardHover"
      style={{
        borderColor: isFailed ? "#FCA5A5" : "#DDE5F0",
        borderLeft: isFailed ? "3px solid #EF4444" : `3px solid ${accent}`,
      }}
    >
      <div className="text-sm font-medium text-ink-900 leading-snug line-clamp-2">
        {truncate(item.title, 80) || `#${item.id}`}
      </div>
      <div className="mt-1 text-xs text-ink-500 flex items-center gap-1.5 flex-wrap">
        {item.author && <span className="truncate max-w-[100px]">{item.author}</span>}
        {item.subsystem && (
          <>
            <span>·</span>
            <Tag className="!m-0 !text-[10px] !leading-tight !px-1" color="blue">
              {item.subsystem}
            </Tag>
          </>
        )}
        {item.version > 1 && (
          <Tag className="!m-0 !text-[10px] !leading-tight !px-1" color="orange">
            v{item.version}
          </Tag>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between gap-1.5">
        <ItemStatusBadge status={item.status} />
        {item.stage_no === 2 && item.merged_upstream !== null && (
          <Tag
            className="!m-0 !text-[10px] !leading-tight !px-1"
            color={item.merged_upstream ? "success" : "warning"}
          >
            {item.merged_upstream ? "已合入上游" : "未合入"}
          </Tag>
        )}
      </div>

      {isFailed && item.error_message && (
        <div className="mt-1.5 text-xs text-red-600 line-clamp-2">
          {truncate(item.error_message, 80)}
        </div>
      )}

      {(showViewOutput || canRetry) && (
        <div
          className="mt-2 flex items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          {showViewOutput && (
            <Button
              size="small"
              type="link"
              icon={<EyeOutlined />}
              onClick={onViewOutput}
              className="!px-0 !text-xs"
            >
              查看产出
            </Button>
          )}
          {canRetry && (
            <Tooltip title={isSuccess ? "基于此版本重新生成" : "重新尝试该条目"}>
              <Button
                size="small"
                type="link"
                danger={isFailed}
                icon={<ReloadOutlined />}
                onClick={onRetry}
                className="!px-0 !ml-auto !text-xs"
              >
                重试
              </Button>
            </Tooltip>
          )}
        </div>
      )}
    </div>
  );
}
