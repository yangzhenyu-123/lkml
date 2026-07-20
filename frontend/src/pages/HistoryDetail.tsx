import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Modal,
  Spin,
  Tag,
  message,
} from "antd";
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  DownOutlined,
  UpOutlined,
} from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import { historyApi } from "@/api/history";
import { JobStatusBadge } from "@/components/StatusBadge";
import OutputViewer from "@/components/OutputViewer";
import StageColumn from "@/components/History/StageColumn";
import ItemDrawer from "@/components/History/ItemDrawer";
import { useJobStream } from "@/components/History/useJobStream";
import { useAuthStore } from "@/store/authStore";
import { formatDateTime, fromNow, stageMeta } from "@/utils/format";
import type {
  AnalysisJob,
  JobItem,
  StageRecord,
  WsLogPayload,
} from "@/types";

const API_BASE = (import.meta.env.VITE_API_BASE as string) || "";
const STAGE_NOS: Array<1 | 2 | 3 | 4> = [1, 2, 3, 4];
// job 终态：进入终态后停止轮询
const TERMINAL_STATUS: ReadonlyArray<AnalysisJob["status"]> = [
  "completed",
  "failed",
];

// 日志级别配色
const LOG_LEVEL_COLOR: Record<WsLogPayload["level"], string> = {
  info: "#3B82F6",
  warn: "#F59E0B",
  error: "#EF4444",
  success: "#10B981",
};
const LOG_LEVEL_TAG: Record<WsLogPayload["level"], string> = {
  info: "INFO",
  warn: "WARN",
  error: "ERR ",
  success: "OK  ",
};

export default function HistoryDetail() {
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [stages, setStages] = useState<StageRecord[]>([]);
  const [items, setItems] = useState<JobItem[]>([]);
  const [activeItem, setActiveItem] = useState<JobItem | null>(null);
  const [retrying, setRetrying] = useState(false);

  // 实时日志面板状态
  const [logs, setLogs] = useState<WsLogPayload[]>([]);
  const [logPanelOpen, setLogPanelOpen] = useState(true);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  // OutputViewer 顶层状态：卡片与抽屉的"查看产出"都通过此触发
  const [outputOpen, setOutputOpen] = useState(false);
  const [outputLoading, setOutputLoading] = useState(false);
  const [outputContent, setOutputContent] = useState<string | undefined>(undefined);
  const [outputError, setOutputError] = useState<string | undefined>(undefined);
  const [outputTitle, setOutputTitle] = useState("产出查看");

  const appendLog = useCallback((entry: WsLogPayload) => {
    setLogs((prev) => {
      // 限制最多 500 条避免内存爆炸
      const next = [...prev, entry];
      return next.length > 500 ? next.slice(next.length - 500) : next;
    });
  }, []);

  // 自动滚动到最新日志
  useEffect(() => {
    if (logPanelOpen && logEndRef.current) {
      logEndRef.current.scrollTop = logEndRef.current.scrollHeight;
    }
  }, [logs, logPanelOpen]);

  const fetchDetail = useCallback(async () => {
    if (!Number.isFinite(jobId)) return;
    setLoading(true);
    try {
      const resp = await historyApi.detail(jobId);
      setJob(resp.job);
      setStages(resp.stages);
      setItems(resp.items);
    } catch {
      message.error("加载任务详情失败");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const { connected } = useJobStream(jobId, {
    setJob,
    setStages,
    setItems,
    setActiveItem,
    appendLog,
  });

  // ============ 轮询兜底 ============
  // 即便 WebSocket 因字段不匹配、连接失败、事件丢失等问题失效，
  // 只要 job 还在非终态，每 3 秒轮询一次详情接口，确保 UI 最终能反映任务结束。
  // 这解决了"任务已完成但前端一直转圈"的根因。
  const jobIsTerminal = job ? TERMINAL_STATUS.includes(job.status) : false;
  useEffect(() => {
    if (jobIsTerminal) return; // 已终态，停止轮询
    const timer = window.setInterval(async () => {
      try {
        const resp = await historyApi.detail(jobId);
        setJob(resp.job);
        setStages(resp.stages);
        setItems(resp.items);
      } catch {
        // 静默失败，下一轮再试
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobId, jobIsTerminal]);

  const itemsByStage = useMemo(() => {
    const map: Record<number, JobItem[]> = { 1: [], 2: [], 3: [], 4: [] };
    items.forEach((it) => {
      const arr = map[it.stage_no];
      if (arr) arr.push(it);
    });
    return map;
  }, [items]);

  const stageByNo = useMemo(() => {
    const map: Record<number, StageRecord | undefined> = {};
    stages.forEach((s) => {
      map[s.stage_no] = s;
    });
    return map;
  }, [stages]);

  // 产出查看：output_path 为后端文件路径，前端无法直接读取。
  // 通过 GET /api/v1/history/jobs/{jobId}/items/{itemId}/output 拉取文本内容。
  const handleViewOutput = useCallback(async (item: JobItem) => {
    setOutputTitle(`阶段${item.stage_no} 产出 · #${item.id}`);
    setOutputOpen(true);
    setOutputLoading(true);
    setOutputError(undefined);
    setOutputContent(undefined);
    const token = useAuthStore.getState().token;
    const url = `${API_BASE}/api/v1/history/jobs/${item.job_id}/items/${item.id}/output`;
    try {
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setOutputContent(await resp.text());
    } catch (err) {
      setOutputError((err as Error).message);
    } finally {
      setOutputLoading(false);
    }
  }, []);

  const handleRetry = useCallback(
    (item: JobItem) => {
      Modal.confirm({
        title: "确认重试该条目？",
        content: `将基于 #${item.id}（v${item.version}）创建新版本并重新执行。`,
        okText: "确认重试",
        cancelText: "取消",
        onOk: async () => {
          setRetrying(true);
          try {
            await historyApi.retryItem(jobId, item.stage_no, item.id);
            message.success("已创建新版本，开始重试");
          } finally {
            setRetrying(false);
          }
        },
      });
    },
    [jobId]
  );

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="space-y-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/history")}>
          返回列表
        </Button>
        <Alert type="warning" message="未找到该任务" />
      </div>
    );
  }

  const currentStageMeta =
    job.current_stage >= 1 && job.current_stage <= 4 ? stageMeta[job.current_stage - 1] : null;

  return (
    <div className="space-y-4">
      {/* 顶部信息区 */}
      <Card variant="borderless" className="lk-card">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                icon={<ArrowLeftOutlined />}
                size="small"
                onClick={() => navigate("/history")}
              >
                返回
              </Button>
              <h1 className="font-display text-2xl font-bold text-ink-900 !m-0">{job.name}</h1>
              <JobStatusBadge status={job.status} />
              {currentStageMeta && (
                <Tag color="processing">
                  {currentStageMeta.icon} 阶段{currentStageMeta.no} · {currentStageMeta.name}
                </Tag>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-ink-600">
              <span>
                时间范围：
                <span className="mono text-ink-900">
                  {job.year_start} - {job.year_end}
                </span>
              </span>
              {job.subsystem_filter && (
                <span>
                  子系统：<Tag className="!m-0 !text-xs">{job.subsystem_filter}</Tag>
                </span>
              )}
              {job.keyword_filter && (
                <span>
                  关键词：<span className="text-ink-700">{job.keyword_filter}</span>
                </span>
              )}
              <span>
                创建于：{fromNow(job.created_at)}（{formatDateTime(job.created_at)}）
              </span>
              {job.started_at && <span>开始：{formatDateTime(job.started_at)}</span>}
              {job.finished_at && <span>结束：{formatDateTime(job.finished_at)}</span>}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <Tag
              color={connected ? "success" : "default"}
              className="!flex !items-center !gap-1.5"
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: connected ? "#10B981" : "#9CA3AF" }}
              />
              {connected ? "实时已连接" : "未连接"}
            </Tag>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={fetchDetail}
              loading={retrying}
            >
              刷新
            </Button>
          </div>
        </div>

        {job.error_message && (
          <Alert
            type="error"
            showIcon
            className="!mt-3"
            message="任务失败"
            description={<div className="text-xs whitespace-pre-wrap">{job.error_message}</div>}
          />
        )}
      </Card>

      {/* 4 阶段流水线 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {STAGE_NOS.map((no, idx) => (
          <StageColumn
            key={no}
            stage={stageByNo[no]}
            items={itemsByStage[no] ?? []}
            showArrow={idx < 3}
            onItemClick={setActiveItem}
            onRetry={handleRetry}
            onViewOutput={handleViewOutput}
          />
        ))}
      </div>

      {/* 实时日志面板 */}
      <Card
        variant="borderless"
        className="lk-card"
        size="small"
        title={
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              实时日志 {logs.length > 0 && <Tag className="!ml-1">{logs.length}</Tag>}
            </span>
            <Button
              size="small"
              type="text"
              onClick={() => setLogPanelOpen((v) => !v)}
              icon={logPanelOpen ? <UpOutlined /> : <DownOutlined />}
            >
              {logPanelOpen ? "收起" : "展开"}
            </Button>
          </div>
        }
      >
        {logPanelOpen && (
          <div
            ref={logEndRef}
            className="bg-gray-900 text-gray-100 text-xs mono rounded p-3 overflow-auto"
            style={{ maxHeight: 320, minHeight: 80 }}
          >
            {logs.length === 0 ? (
              <div className="text-gray-400">
                暂无日志输出。任务运行中会实时打印 pipeline 各阶段的执行进度...
              </div>
            ) : (
              logs.map((entry, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all">
                  <span className="text-gray-500">[{entry.ts.slice(11, 19)}]</span>{" "}
                  <span style={{ color: LOG_LEVEL_COLOR[entry.level] }}>
                    {LOG_LEVEL_TAG[entry.level]}
                  </span>{" "}
                  {entry.stage_no !== null && (
                    <span className="text-purple-300">[S{entry.stage_no}]</span>
                  )}{" "}
                  <span>{entry.message}</span>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      <ItemDrawer
        item={activeItem}
        onClose={() => setActiveItem(null)}
        onRetry={handleRetry}
        onViewOutput={handleViewOutput}
      />

      <OutputViewer
        open={outputOpen}
        title={outputTitle}
        loading={outputLoading}
        error={outputError}
        content={outputContent}
        onClose={() => setOutputOpen(false)}
      />
    </div>
  );
}
