import { useCallback } from "react";
import { message } from "antd";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { AnalysisJob, JobItem, StageRecord, WsEvent } from "@/types";

type SetJob = (updater: (j: AnalysisJob | null) => AnalysisJob | null) => void;
type SetStages = (updater: (prev: StageRecord[]) => StageRecord[]) => void;
type SetItems = (updater: (prev: JobItem[]) => JobItem[]) => void;
type SetActiveItem = (updater: (ai: JobItem | null) => JobItem | null) => void;

interface Setters {
  setJob: SetJob;
  setStages: SetStages;
  setItems: SetItems;
  setActiveItem: SetActiveItem;
}

/**
 * 订阅 /history/jobs/{jobId}/stream，将 job/stage/item 实时事件应用到本地状态。
 * 组件卸载时由 useWebSocket 自动断开。
 */
export function useJobStream(jobId: number, setters: Setters) {
  const { setJob, setStages, setItems, setActiveItem } = setters;

  const handleMessage = useCallback(
    (msg: WsEvent) => {
      if (msg.event === "job_update") {
        setJob((j) =>
          j ? { ...j, status: msg.status, current_stage: msg.current_stage } : j
        );
        if (msg.status === "completed") message.success("任务已完成");
        else if (msg.status === "failed") message.error("任务执行失败");
      } else if (msg.event === "stage_update") {
        setStages((prev) =>
          prev.map((s) =>
            s.stage_no === msg.stage_no
              ? {
                  ...s,
                  status: msg.status,
                  success_items: msg.success_items,
                  failed_items: msg.failed_items,
                  total_items: msg.total_items,
                }
              : s
          )
        );
        if (msg.status === "completed") message.success(`阶段${msg.stage_no} 完成`);
        else if (msg.status === "failed") message.error(`阶段${msg.stage_no} 失败`);
      } else if (msg.event === "item_update") {
        const patch = {
          status: msg.status,
          version: msg.version,
          output_path: msg.output_path,
          error_message: msg.error_message,
          token_usage: msg.token_usage,
        };
        setItems((prev) => prev.map((it) => (it.id === msg.item_id ? { ...it, ...patch } : it)));
        setActiveItem((ai) => (ai && ai.id === msg.item_id ? { ...ai, ...patch } : ai));
        if (msg.status === "failed") message.warning(`条目 #${msg.item_id} 失败`);
        else if (msg.status === "success") message.success(`条目 #${msg.item_id} 完成`);
      }
    },
    [setJob, setStages, setItems, setActiveItem]
  );

  return useWebSocket<WsEvent>(
    Number.isFinite(jobId) ? `/history/jobs/${jobId}/stream` : null,
    handleMessage
  );
}
