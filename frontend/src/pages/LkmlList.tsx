import { useCallback, useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  DatePicker,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
} from "antd";
import { ReloadOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { lkmlApi } from "@/api/lkml";
import { formatDateTime, truncate } from "@/utils/format";
import type { Email } from "@/types";

const SUBSYSTEMS = ["sched", "mm", "net", "fs", "block", "drivers", "generic"];
const PAGE_SIZE = 20;
type RangeValue = [Dayjs | null, Dayjs | null] | null;

export default function LkmlList() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const q = searchParams.get("q") || "";
  const subsystem = searchParams.get("subsystem") || undefined;
  const page = parseInt(searchParams.get("page") || "1", 10);

  const [qInput, setQInput] = useState(q);
  const [subsystemInput, setSubsystemInput] = useState<string | undefined>(subsystem);
  const [isPatch, setIsPatch] = useState(false);
  const [dateRange, setDateRange] = useState<RangeValue>(null);

  const [items, setItems] = useState<Email[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const [syncOpen, setSyncOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncForm] = Form.useForm<{ year_month?: string }>();

  useEffect(() => {
    setQInput(q);
  }, [q]);
  useEffect(() => {
    setSubsystemInput(subsystem);
  }, [subsystem]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Parameters<typeof lkmlApi.list>[0] = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      if (q) params.q = q;
      if (subsystem) params.subsystem = subsystem;
      if (isPatch) params.is_patch = true;
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.start_date = dateRange[0].format("YYYY-MM-DD");
        params.end_date = dateRange[1].format("YYYY-MM-DD");
      }
      const resp = await lkmlApi.list(params);
      setItems(resp.items);
      setTotal(resp.total);
    } finally {
      setLoading(false);
    }
  }, [page, q, subsystem, isPatch, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const updateUrl = (next: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams);
    Object.entries(next).forEach(([k, v]) => {
      if (v === undefined || v === "") params.delete(k);
      else params.set(k, v);
    });
    setSearchParams(params);
  };

  const handleSearch = () => {
    updateUrl({
      q: qInput || undefined,
      subsystem: subsystemInput,
      page: undefined,
    });
  };

  const handleReset = () => {
    setQInput("");
    setSubsystemInput(undefined);
    setIsPatch(false);
    setDateRange(null);
    updateUrl({ q: undefined, subsystem: undefined, page: undefined });
  };

  const handleSync = async () => {
    try {
      const values = await syncForm.validateFields();
      setSyncing(true);
      const yearMonth = values.year_month?.trim() || undefined;
      const resp = await lkmlApi.sync({ year_month: yearMonth });
      message.success(resp.message || `同步任务已提交：${resp.task_id}`);
      setSyncOpen(false);
      syncForm.resetFields();
    } catch {
      // 校验失败或接口异常（接口异常已由拦截器提示）
    } finally {
      setSyncing(false);
    }
  };

  const columns: ColumnsType<Email> = [
    {
      title: "主题",
      dataIndex: "subject",
      key: "subject",
      render: (_, r) => (
        <Link
          to={`/lkml/${encodeURIComponent(r.message_id)}`}
          onClick={(e) => e.stopPropagation()}
        >
          <span className="text-ink-900 hover:text-ember-600 transition-colors">
            {truncate(r.subject, 60)}
          </span>
        </Link>
      ),
    },
    {
      title: "作者",
      dataIndex: "author",
      key: "author",
      width: 200,
      ellipsis: true,
      render: (a: string) => <span className="text-ink-700 text-sm">{a}</span>,
    },
    {
      title: "子系统",
      dataIndex: "subsystem",
      key: "subsystem",
      width: 110,
      render: (s: string | null) =>
        s ? <Tag color="blue">{s}</Tag> : <span className="text-ink-300">—</span>,
    },
    {
      title: "PATCH",
      dataIndex: "is_patch",
      key: "is_patch",
      width: 80,
      align: "center",
      render: (v: boolean) =>
        v ? <span className="text-ember-600 font-semibold">✓</span> : "",
    },
    {
      title: "回复数",
      dataIndex: "reply_count",
      key: "reply_count",
      width: 90,
      align: "right",
      render: (n: number) => <span className="text-ink-600 text-sm">{n}</span>,
    },
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 150,
      render: (s: string) => (
        <span className="text-ink-500 text-xs">{formatDateTime(s)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900 m-0">
            LKML 邮件归档
          </h1>
          <p className="text-ink-500 text-sm mt-1">
            浏览 Linux 内核邮件列表存档，识别性能优化类 PATCH
          </p>
        </div>
        <Button icon={<SyncOutlined />} onClick={() => setSyncOpen(true)}>
          手动同步
        </Button>
      </div>

      <Card variant="borderless" className="lk-card">
        <div className="flex flex-wrap items-center gap-3">
          <Input.Search
            placeholder="搜索关键词（标题/作者/正文）"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            onSearch={handleSearch}
            allowClear
            style={{ width: 280 }}
            prefix={<SearchOutlined className="text-ink-300" />}
          />
          <Select
            placeholder="子系统"
            value={subsystemInput}
            onChange={setSubsystemInput}
            allowClear
            style={{ width: 140 }}
            options={SUBSYSTEMS.map((s) => ({ label: s, value: s }))}
          />
          <DatePicker.RangePicker
            value={dateRange}
            onChange={(v) => setDateRange(v)}
            placeholder={["开始日期", "结束日期"]}
          />
          <Space size="small">
            <span className="text-ink-500 text-sm">仅 PATCH</span>
            <Switch checked={isPatch} onChange={setIsPatch} />
          </Space>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
              查询
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置
            </Button>
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="lk-card !p-0 overflow-hidden">
        <Spin spinning={loading}>
          <Table<Email>
            rowKey="message_id"
            columns={columns}
            dataSource={items}
            size="middle"
            pagination={{
              current: page,
              pageSize: PAGE_SIZE,
              total,
              showTotal: (t) => `共 ${t} 封邮件`,
              onChange: (p) =>
                updateUrl({ page: p === 1 ? undefined : String(p) }),
            }}
            onRow={(r) => ({
              onClick: () =>
                navigate(`/lkml/${encodeURIComponent(r.message_id)}`),
              style: { cursor: "pointer" },
            })}
            locale={{ emptyText: <Empty description="暂无邮件" /> }}
            scroll={{ x: 900 }}
          />
        </Spin>
      </Card>

      <Modal
        open={syncOpen}
        title="手动同步 LKML"
        onCancel={() => setSyncOpen(false)}
        onOk={handleSync}
        confirmLoading={syncing}
        okText="开始同步"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={syncForm} layout="vertical" preserve={false}>
          <Form.Item
            name="year_month"
            label="同步月份"
            rules={[
              {
                pattern: /^\d{4}-\d{2}$/,
                message: "格式必须为 YYYY-MM，例如 2024-05",
              },
            ]}
            extra="留空则同步最新月份"
          >
            <Input placeholder="例如：2024-05" style={{ width: 200 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
