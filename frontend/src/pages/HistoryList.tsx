import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Slider,
  Spin,
  Table,
  Tag,
  message,
} from "antd";
import { PlusOutlined, EyeOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { historyApi } from "@/api/history";
import { JobStatusBadge } from "@/components/StatusBadge";
import { fromNow, jobStatusMap, stageMeta } from "@/utils/format";
import type { AnalysisJob, AnalysisJobCreate, JobStatus } from "@/types";

// 预置子系统列表（与后端 lkml_sync.py 的 _SUBSYSTEM_KEYWORDS 对齐）
const SUBSYSTEM_OPTIONS = [
  { label: "调度器 (sched)", value: "sched" },
  { label: "内存管理 (mm)", value: "mm" },
  { label: "网络 (net)", value: "net" },
  { label: "文件系统 (fs)", value: "fs" },
  { label: "块层 (block)", value: "block" },
  { label: "驱动 (drivers)", value: "drivers" },
  { label: "架构 (arch)", value: "arch" },
  { label: "锁机制 (locking)", value: "locking" },
  { label: "追踪 (tracing)", value: "tracing" },
  { label: "安全 (security)", value: "security" },
];

// 预置性能相关关键词（与后端 _PERF_KEYWORDS 对齐）
const KEYWORD_OPTIONS = [
  { label: "performance", value: "performance" },
  { label: "latency", value: "latency" },
  { label: "throughput", value: "throughput" },
  { label: "optimization", value: "optimization" },
  { label: "scalability", value: "scalability" },
  { label: "benchmark", value: "benchmark" },
  { label: "speedup", value: "speedup" },
  { label: "faster", value: "faster" },
  { label: "hot path", value: "hot path" },
  { label: "slow path", value: "slow path" },
  { label: "overhead", value: "overhead" },
  { label: "cache miss", value: "cache miss" },
  { label: "batch", value: "batch" },
];

const CURRENT_YEAR = new Date().getFullYear();
// 年份范围：LKML 最早 1991（Linux 诞生），最晚当前年份
const YEAR_MIN = 1991;
const YEAR_MAX = CURRENT_YEAR;
const YEAR_MARKS = {
  [YEAR_MIN]: "1991",
  2000: "2000",
  2010: "2010",
  2020: "2020",
  [YEAR_MAX]: String(YEAR_MAX),
};

const PAGE_SIZE = 20;

const statusOptions = [
  { label: "全部状态", value: "" },
  ...(Object.entries(jobStatusMap) as [JobStatus, { color: string; text: string }][]).map(
    ([value, m]) => ({ label: m.text, value })
  ),
];

export default function HistoryList() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<unknown>();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await historyApi.list({
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        status: status || undefined,
      });
      setJobs(resp.items);
      setTotal(resp.total);
    } finally {
      setLoading(false);
    }
  }, [page, status]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    type CreateFormValues = {
      name: string;
      year_range: [number, number];
      subsystems: string[];
      keywords: string[];
      extra_keywords?: string;
    };
    let values: CreateFormValues;
    try {
      values = await form.validateFields() as CreateFormValues;
    } catch {
      return; // 校验失败，表单自身已显示错误
    }
    // 合并预置关键词与额外关键词
    const extraList = (values.extra_keywords || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const allKeywords = [...values.keywords, ...extraList];
    const payload: AnalysisJobCreate = {
      name: values.name,
      year_start: values.year_range[0],
      year_end: values.year_range[1],
      subsystem_filter: values.subsystems.length > 0 ? values.subsystems.join(",") : undefined,
      keyword_filter: allKeywords.length > 0 ? allKeywords.join(",") : undefined,
    };
    setSubmitting(true);
    try {
      const job = await historyApi.create(payload);
      message.success("任务已创建，开始进入详情");
      setModalOpen(false);
      form.resetFields();
      navigate(`/history/${job.id}`);
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      title: "任务名称",
      dataIndex: "name",
      key: "name",
      render: (_: string, r: AnalysisJob) => (
        <Link to={`/history/${r.id}`} className="font-medium text-ink-900 hover:text-ember-600">
          {r.name}
        </Link>
      ),
    },
    {
      title: "时间范围",
      key: "range",
      render: (_: unknown, r: AnalysisJob) => (
        <span className="mono text-xs text-ink-700">
          {r.year_start} - {r.year_end}
        </span>
      ),
    },
    {
      title: "子系统筛选",
      dataIndex: "subsystem_filter",
      key: "subsystem_filter",
      render: (v: string | null) =>
        v ? <Tag className="!m-0">{v}</Tag> : <span className="text-ink-400">—</span>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (s: JobStatus) => <JobStatusBadge status={s} />,
    },
    {
      title: "当前阶段",
      dataIndex: "current_stage",
      key: "current_stage",
      render: (n: number) => {
        if (!n || n < 1 || n > 4) return <span className="text-ink-400">—</span>;
        const m = stageMeta[n - 1];
        return (
          <span className="text-xs text-ink-700">
            <span className="mr-1">{m.icon}</span>
            阶段{m.no} · {m.name}
          </span>
        );
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (s: string) => <span className="text-ink-500 text-xs">{fromNow(s)}</span>,
    },
    {
      title: "操作",
      key: "action",
      width: 96,
      render: (_: unknown, r: AnalysisJob) => (
        <Link to={`/history/${r.id}`}>
          <Button type="link" size="small" icon={<EyeOutlined />}>
            查看
          </Button>
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">历史分析任务</h1>
          <p className="mt-1 text-sm text-ink-500">
            从 LKML 历史邮件中挖掘可申请专利的性能优化方案
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
          className="lk-btn-ember"
        >
          新建分析任务
        </Button>
      </div>

      <Card variant="borderless" className="lk-card">
        <div className="mb-4 flex items-center gap-3">
          <span className="text-sm text-ink-600">状态筛选：</span>
          <Select
            value={status}
            onChange={(v) => {
              setStatus(v);
              setPage(1);
            }}
            options={statusOptions}
            className="w-48"
          />
        </div>
        <Spin spinning={loading}>
          <Table
            rowKey="id"
            dataSource={jobs}
            columns={columns}
            pagination={{
              current: page,
              pageSize: PAGE_SIZE,
              total,
              onChange: (p) => setPage(p),
              showTotal: (t) => `共 ${t} 个任务`,
            }}
            locale={{
              emptyText: (
                <span className="text-ink-400">暂无分析任务，点击右上角"新建分析任务"开始</span>
              ),
            }}
          />
        </Spin>
      </Card>

      <Modal
        title="新建分析任务"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleCreate}
        confirmLoading={submitting}
        okText="创建并进入"
        cancelText="取消"
        destroyOnClose
        width={720}
      >
        <Form
          form={form}
          layout="vertical"
          className="mt-2"
          preserve={false}
          initialValues={{
            year_range: [CURRENT_YEAR - 2, CURRENT_YEAR],
            subsystems: [],
            keywords: [],
          }}
        >
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: "请输入任务名称" }]}
          >
            <Input placeholder="例如：2023 年调度器优化挖掘" />
          </Form.Item>

          <Form.Item
            name="year_range"
            label="年份范围"
            tooltip="拖动滑块选择起止年份（含两端）"
            rules={[{ required: true, message: "请选择年份范围" }]}
          >
            <Slider
              range
              min={YEAR_MIN}
              max={YEAR_MAX}
              marks={YEAR_MARKS}
              step={1}
              tooltip={{ formatter: (v) => `${v} 年` }}
            />
          </Form.Item>

          <Form.Item name="subsystems" label="子系统筛选（可多选）">
            <Checkbox.Group options={SUBSYSTEM_OPTIONS} className="flex flex-wrap gap-2" />
          </Form.Item>

          <Form.Item name="keywords" label="关键词（可多选，预置性能相关）">
            <Checkbox.Group options={KEYWORD_OPTIONS} className="flex flex-wrap gap-2" />
          </Form.Item>

          <Form.Item name="extra_keywords" label="额外关键词（可选，逗号分隔）">
            <Input placeholder="例如：rcu, lockless, numa" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
