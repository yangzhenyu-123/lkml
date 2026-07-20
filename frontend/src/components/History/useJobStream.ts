import { useCallback } from "react";
import { message } from "antd";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  AnalysisJob,
  JobItem,
  StageRecord,
  WsEvent,
  WsItemUpdatePayload,
  WsJobUpdatePayload,
  WsLogPayload,
  WsSnapshotPayload,
  WsStageUpdatePayload,
} from "@/types";

type SetJob = (updater: (j: AnalysisJob | null) => AnalysisJob | null) => void;
type SetStages = (updater: (prev: StageRecord[]) => StageRecord[]) => void;
type SetItems = (updater: (prev: JobItem[]) => JobItem[]) => void;
type SetActiveItem = (updater: (ai: JobItem | null) => JobItem | null) => void;
type AppendLog = (entry: WsLogPayload) => void;

interface Setters {
  setJob: SetJob;
  setStages: SetStages;
  setItems: SetItems;
  setActiveItem: SetActiveItem;
  appendLog: AppendLog;
}

/**
 * 订阅 /history/jobs/{jobId}/stream，将 job/stage/item 实时事件应用到本地状态。
 *
 * 协议：{ type: "job_update"|"stage_update"|"item_update"|"log"|"snapshot"|"connected",
 *        job_id: number, payload?: {...} }
 *
 * - snapshot: 连接建立后立即推送一次，包含 job + stages + items 当前完整状态
 *             （解决"任务瞬间完成、WS 没连上就错过事件"的转圈问题）
 * - log:     pipeline 各阶段进度日志，前端实时日志面板使用
 */
export function useJobStream(jobId: number, setters: Setters) {
  const { setJob, setStages, setItems, setActiveItem, appendLog } = setters;

  const handleMessage = useCallback(
    (msg: WsEvent) => {
      switch (msg.type) {
        case "snapshot": {
          const snap = msg.payload as unknown as WsSnapshotPayload;
          if (snap?.job) setJob(() => snap.job);
          if (snap?.stages) setStages(() => snap.stages);
          if (snap?.items) setItems(() => snap.items);
          // snapshot 不弹 message，避免重复提示
          break;
        }
        case "job_update": {
          const p = msg.payload as unknown as WsJobUpdatePayload;
          if (!p) break;
          setJob((j) =>
            j
              ? {
                  ...j,
                  status: p.status,
                  current_stage: p.current_stage ?? j.current_stage,
                  error_message: p.error_message ?? j.error_message,
                }
              : j
          );
          if (p.status === "completed") message.success("任务已完成");
          else if (p.status === "failed") message.error("任务执行失败");
          break;
        }
        case "stage_update": {
          const p = msg.payload as unknown as WsStageUpdatePayload;
          if (!p) break;
          setStages((prev) =>
            prev.map((s) =>
              s.stage_no === p.stage_no
                ? {
                    ...s,
                    status: p.status,
                    success_items: p.success_items ?? s.success_items,
                    failed_items: p.failed_items ?? s.failed_items,
                    total_items: p.total_items ?? s.total_items,
                  }
                : s
            )
          );
          if (p.status === "completed") message.success(`阶段${p.stage_no} 完成`);
          else if (p.status === "failed") message.error(`阶段${p.stage_no} 失败`);
          break;
        }
        case "item_update": {
          const p = msg.payload as unknown as WsItemUpdatePayload;
          if (!p) break;
          const patch: Partial<JobItem> = {
            status: p.status,
            version: p.version,
            output_path: p.output_path,
            error_message: p.error_message,
            token_usage: p.token_usage ?? 0,
          };
          setItems((prev) =>
            prev.map((it) => (it.id === p.item_id ? { ...it, ...patch } : it))
          );
          setActiveItem((ai) =>
            ai && ai.id === p.item_id ? { ...ai, ...patch } : ai
          );
          if (p.status === "failed") message.warning(`条目 #${p.item_id} 失败`);
          else if (p.status === "success") message.success(`条目 #${p.item_id} 完成`);
          break;
        }
        case "log": {
          const p = msg.payload as unknown as WsLogPayload;
          if (p) appendLog(p);
          break;
        }
        case "connected":
          // 仅确认连接，无需处理
          break;
      }
    },
    [setJob, setStages, setItems, setActiveItem, appendLog]
  );

  return useWebSocket<WsEvent>(
    Number.isFinite(jobId) ? `/history/jobs/${jobId}/stream` : null,
    handleMessage
  );
}
