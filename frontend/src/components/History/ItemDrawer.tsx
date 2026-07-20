import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Tag,
  Tooltip,
} from "antd";
import { EyeOutlined, ReloadOutlined } from "@ant-design/icons";
import { ItemStatusBadge } from "@/components/StatusBadge";
import { formatDateTime, stageMeta } from "@/utils/format";
import { STAGE_COLORS } from "./stageColors";
import type { JobItem } from "@/types";

interface Props {
  item: JobItem | null;
  onClose: () => void;
  onRetry: (item: JobItem) => void;
  onViewOutput: (item: JobItem) => void;
}

export default function ItemDrawer({ item, onClose, onRetry, onViewOutput }: Props) {
  if (!item) {
    return (
      <Drawer open={false} onClose={onClose} width={560}>
        {null}
      </Drawer>
    );
  }

  const meta = stageMeta[item.stage_no - 1];
  const accent = STAGE_COLORS[item.stage_no];
  const canRetry = meta.retryable && (item.status === "failed" || item.status === "success");
  const canViewOutput =
    item.status === "success" && (item.stage_no === 3 || item.stage_no === 4);

  return (
    <Drawer
      open={!!item}
      onClose={onClose}
      width={560}
      title={
        <div className="flex items-center gap-2">
          <span>{meta.icon}</span>
          <span className="font-display font-semibold">条目 #{item.id}</span>
          <Tag style={{ color: accent, borderColor: accent }} className="!ml-1">
            阶段{meta.no}
          </Tag>
        </div>
      }
      extra={
        canViewOutput ? (
          <Button
            type="primary"
            icon={<EyeOutlined />}
            onClick={() => onViewOutput(item)}
            size="small"
          >
            查看产出
          </Button>
        ) : null
      }
    >
      <div className="space-y-4">
        <div>
          <div className="text-xs text-ink-500 mb-1">标题</div>
          <div className="font-medium text-ink-900 leading-snug">
            {item.title || `#${item.id}`}
          </div>
        </div>

        {item.error_message && (
          <Alert
            type="error"
            showIcon
            message="执行失败"
            description={
              <div className="text-xs whitespace-pre-wrap break-all">
                {item.error_message}
              </div>
            }
          />
        )}

        <Descriptions
          column={2}
          size="small"
          bordered
          labelStyle={{ width: 96, background: "#EEF2F8" }}
        >
          <Descriptions.Item label="状态">
            <ItemStatusBadge status={item.status} />
          </Descriptions.Item>
          <Descriptions.Item label="版本">
            <Tag color={item.version > 1 ? "orange" : "default"}>v{item.version}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="作者">{item.author || "—"}</Descriptions.Item>
          <Descriptions.Item label="子系统">
            {item.subsystem ? <Tag color="blue">{item.subsystem}</Tag> : "—"}
          </Descriptions.Item>
          {item.stage_no === 2 && (
            <Descriptions.Item label="上游合入" span={2}>
              {item.merged_upstream === null ? (
                "—"
              ) : (
                <Tag color={item.merged_upstream ? "success" : "warning"}>
                  {item.merged_upstream ? "已合入上游" : "未合入上游"}
                </Tag>
              )}
            </Descriptions.Item>
          )}
          {item.optimization_type && (
            <Descriptions.Item label="优化类型" span={2}>
              <Tag color="gold">{item.optimization_type}</Tag>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="Token 用量" span={2}>
            <span className="mono text-xs">{item.token_usage.toLocaleString()}</span>
          </Descriptions.Item>
          {item.patch_id && (
            <Descriptions.Item label="Patch ID" span={2}>
              <span className="mono text-xs text-ember-600 break-all">{item.patch_id}</span>
            </Descriptions.Item>
          )}
          {item.parent_item_id !== null && (
            <Descriptions.Item label="父版本" span={2}>
              <Tag color="purple">#{item.parent_item_id}</Tag>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="开始时间">
            <span className="text-xs">{formatDateTime(item.started_at)}</span>
          </Descriptions.Item>
          <Descriptions.Item label="结束时间">
            <span className="text-xs">{formatDateTime(item.finished_at)}</span>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间" span={2}>
            <span className="text-xs">{formatDateTime(item.created_at)}</span>
          </Descriptions.Item>
          {item.output_path && (
            <Descriptions.Item label="产出路径" span={2}>
              <span className="mono text-xs text-ink-600 break-all">{item.output_path}</span>
            </Descriptions.Item>
          )}
          {item.log_path && (
            <Descriptions.Item label="日志路径" span={2}>
              <span className="mono text-xs text-ink-600 break-all">{item.log_path}</span>
            </Descriptions.Item>
          )}
          {item.email_message_id && (
            <Descriptions.Item label="邮件 Message-ID" span={2}>
              <span className="mono text-xs text-ink-600 break-all">
                {item.email_message_id}
              </span>
            </Descriptions.Item>
          )}
        </Descriptions>

        {canRetry && (
          <Tooltip
            title={
              item.status === "success"
                ? "基于此版本重新生成新版本"
                : "重新尝试执行该条目"
            }
          >
            <Button
              block
              icon={<ReloadOutlined />}
              danger={item.status === "failed"}
              onClick={() => onRetry(item)}
            >
              {item.status === "success" ? "重新生成新版本" : "重试该条目"}
            </Button>
          </Tooltip>
        )}
      </div>
    </Drawer>
  );
}
