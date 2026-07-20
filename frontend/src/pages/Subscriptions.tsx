import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Spin,
  Switch,
  Tag,
} from "antd";
import { BellOutlined, DeleteOutlined, MailOutlined, PlusOutlined } from "@ant-design/icons";
import { subscriptionsApi } from "@/api/subscriptions";
import type { Subscription, SubscriptionCreate, SubscriptionType } from "@/types";
import { formatDateTime, fromNow } from "@/utils/format";

const typeMeta: Record<SubscriptionType, { icon: string; label: string }> = {
  daily_article: { icon: "📬", label: "每日文章" },
  stage3_output: { icon: "⚡", label: "优化方案产出" },
  stage4_output: { icon: "📜", label: "专利交底书产出" },
  subsystem: { icon: "🎯", label: "指定子系统" },
};

export default function Subscriptions() {
  const { message } = App.useApp();
  const [items, setItems] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<SubscriptionCreate>();
  const currentType = Form.useWatch("type", form);

  const load = async () => {
    setLoading(true);
    try {
      const { items } = await subscriptionsApi.list();
      setItems(items);
    } catch {
      // 错误已由 API 拦截器提示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ type: "daily_article", email_notify: true });
    setOpen(true);
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await subscriptionsApi.create(values);
      message.success("订阅已创建");
      setOpen(false);
      void load();
    } catch {
      // 校验失败或接口错误
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await subscriptionsApi.remove(id);
      message.success("订阅已删除");
      void load();
    } catch {
      // 错误已由 API 拦截器提示
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900 m-0">我的订阅</h1>
          <p className="text-ink-500 text-sm mt-1">关注特定类型的产出，自动接收通知</p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          className="lk-btn-ember"
          onClick={openCreate}
        >
          新建订阅
        </Button>
      </div>

      <Card variant="borderless" className="lk-card">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-ember-100 flex items-center justify-center text-ember-600 text-lg shrink-0">
            <BellOutlined />
          </div>
          <div>
            <div className="font-display font-semibold text-ink-900">订阅功能说明</div>
            <p className="text-sm text-ink-600 mt-1 leading-relaxed">
              当有新的产出落盘时，系统会根据您的订阅自动发送邮件通知。您可以订阅每日文章、优化方案产出、专利交底书产出，或针对指定子系统进行筛选。
            </p>
          </div>
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spin />
        </div>
      ) : items.length === 0 ? (
        <Card variant="borderless" className="lk-card">
          <Empty description="暂无订阅，点击右上角新建一个" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((s) => {
            const meta = typeMeta[s.type];
            return (
              <Card
                key={s.id}
                variant="borderless"
                className="lk-card"
                title={
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{meta.icon}</span>
                    <span className="font-display font-semibold text-ink-900">{meta.label}</span>
                  </div>
                }
                extra={
                  <Popconfirm
                    title="删除订阅"
                    description="确定要删除该订阅吗？"
                    onConfirm={() => handleDelete(s.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                  </Popconfirm>
                }
              >
                <div className="space-y-2 text-sm">
                  {s.type === "subsystem" && (
                    <div className="flex items-start gap-2">
                      <span className="text-ink-500 w-20 shrink-0">子系统筛选</span>
                      <div className="flex flex-wrap gap-1">
                        {(s.subsystem_filter || "")
                          .split(",")
                          .map((p) => p.trim())
                          .filter(Boolean)
                          .map((p) => (
                            <Tag key={p} className="!m-0">
                              {p}
                            </Tag>
                          ))}
                        {!s.subsystem_filter && <span className="text-ink-400">—</span>}
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <span className="text-ink-500 w-20">邮件通知</span>
                    {s.email_notify ? (
                      <Tag color="green" icon={<MailOutlined />}>
                        已开启
                      </Tag>
                    ) : (
                      <Tag>未开启</Tag>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-ink-500 w-20">创建时间</span>
                    <span className="text-ink-800">{formatDateTime(s.created_at)}</span>
                    <span className="text-ink-400 text-xs">({fromNow(s.created_at)})</span>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        title="新建订阅"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleCreate}
        confirmLoading={submitting}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ className: "lk-btn-ember" }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="type"
            label="订阅类型"
            rules={[{ required: true, message: "请选择订阅类型" }]}
          >
            <Select
              placeholder="请选择订阅类型"
              options={Object.entries(typeMeta).map(([k, v]) => ({
                value: k as SubscriptionType,
                label: `${v.icon} ${v.label}`,
              }))}
            />
          </Form.Item>
          {currentType === "subsystem" && (
            <Form.Item
              name="subsystem_filter"
              label="子系统筛选"
              extra="多个子系统用英文逗号分隔，例如 sched,mm,net"
              rules={[{ required: true, message: "请输入子系统筛选" }]}
            >
              <Input placeholder="sched,mm,net" />
            </Form.Item>
          )}
          <Form.Item name="email_notify" label="邮件通知" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
