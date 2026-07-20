import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
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
  const [form] = Form.useForm<AnalysisJobCreate>();

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
    let values: AnalysisJobCreate;
    try {
      values = await form.validateFields();
    } catch {
      return; // 校验失败，表单自身已显示错误
    }
    setSubmitting(true);
    try {
      const job = await historyApi.create(values);
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
        width={560}
      >
        <Form form={form} layout="vertical" className="mt-2" preserve={false}>
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: "请输入任务名称" }]}
          >
            <Input placeholder="例如：2023 年调度器优化挖掘" />
          </Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item
              name="year_start"
              label="起始年份"
              rules={[{ required: true, message: "请输入起始年份" }]}
            >
              <InputNumber className="!w-full" min={1990} max={2100} placeholder="2018" />
            </Form.Item>
            <Form.Item
              name="year_end"
              label="结束年份"
              rules={[{ required: true, message: "请输入结束年份" }]}
            >
              <InputNumber className="!w-full" min={1990} max={2100} placeholder="2024" />
            </Form.Item>
          </div>
          <Form.Item name="subsystem_filter" label="子系统筛选（逗号分隔）">
            <Input placeholder="scheduler, mm, net" />
          </Form.Item>
          <Form.Item name="keyword_filter" label="关键词">
            <Input.TextArea rows={3} placeholder="performance, latency, throughput" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
