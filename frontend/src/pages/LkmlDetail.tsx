import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Space,
  Spin,
  Tag,
  Tooltip,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import { lkmlApi } from "@/api/lkml";
import { formatDateTime, truncate } from "@/utils/format";
import type { Email } from "@/types";

export default function LkmlDetail() {
  const { messageId } = useParams<{ messageId: string }>();
  const navigate = useNavigate();

  const [email, setEmail] = useState<Email | null>(null);
  const [related, setRelated] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!messageId) return;
    setLoading(true);
    (async () => {
      try {
        const data = await lkmlApi.detail(messageId);
        setEmail(data);
        const tasks: Promise<Email[]>[] = [];
        if (data.subsystem) {
          tasks.push(
            lkmlApi
              .list({ subsystem: data.subsystem, limit: 10 })
              .then((r) => r.items),
          );
        }
        if (data.author) {
          tasks.push(
            lkmlApi.list({ q: data.author, limit: 10 }).then((r) => r.items),
          );
        }
        if (tasks.length === 0) {
          setRelated([]);
          return;
        }
        const results = await Promise.all(tasks);
        const seen = new Set<string>([data.message_id]);
        const merged: Email[] = [];
        for (const list of results) {
          for (const e of list) {
            if (!seen.has(e.message_id)) {
              seen.add(e.message_id);
              merged.push(e);
              if (merged.length >= 5) break;
            }
          }
          if (merged.length >= 5) break;
        }
        setRelated(merged);
      } finally {
        setLoading(false);
      }
    })();
  }, [messageId]);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  if (!email) {
    return <Empty description="未找到该邮件" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-xl font-bold text-ink-900 m-0 break-words">
            {email.subject || "(无主题)"}
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card variant="borderless" className="lk-card">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="作者">
                <span className="text-ink-800">{email.author}</span>
              </Descriptions.Item>
              <Descriptions.Item label="日期">
                {formatDateTime(email.date)}
              </Descriptions.Item>
              <Descriptions.Item label="子系统">
                {email.subsystem ? (
                  <Tag color="blue">{email.subsystem}</Tag>
                ) : (
                  <span className="text-ink-300">—</span>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="回复数">
                {email.reply_count}
              </Descriptions.Item>
              <Descriptions.Item label="PATCH">
                {email.is_patch ? (
                  <Tag color="orange">✓ PATCH</Tag>
                ) : (
                  <span className="text-ink-300">—</span>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Patch ID">
                {email.patch_id ? (
                  <code className="text-xs text-ember-600">{email.patch_id}</code>
                ) : (
                  <span className="text-ink-300">—</span>
                )}
              </Descriptions.Item>
            </Descriptions>
            {email.in_reply_to && (
              <div className="mt-3 pt-3 border-t border-ink-100">
                <Link to={`/lkml/${encodeURIComponent(email.in_reply_to)}`}>
                  <Button type="link" size="small" className="!px-0">
                    ↩ 回复上一封：{truncate(email.in_reply_to, 80)}
                  </Button>
                </Link>
              </div>
            )}
          </Card>

          <Card title="邮件正文" variant="borderless" className="lk-card">
            <pre className="font-mono text-sm bg-ink-50 p-4 rounded whitespace-pre-wrap overflow-x-auto text-ink-800">
              {email.body || "(无正文)"}
            </pre>
          </Card>

          {email.refs && email.refs.length > 0 && (
            <Card title="引用链" variant="borderless" className="lk-card">
              <Space wrap>
                {email.refs.map((r, i) => (
                  <Link key={`${r}-${i}`} to={`/lkml/${encodeURIComponent(r)}`}>
                    <Tooltip title={r}>
                      <Tag className="cursor-pointer hover:border-ember-500 hover:text-ember-600 transition-colors">
                        #{i + 1} {truncate(r, 40)}
                      </Tag>
                    </Tooltip>
                  </Link>
                ))}
              </Space>
            </Card>
          )}
        </div>

        <div>
          <Card
            title="相关邮件"
            variant="borderless"
            className="lk-card sticky top-4"
          >
            {related.length === 0 ? (
              <Empty description="无相关邮件" />
            ) : (
              <div className="space-y-2">
                {related.map((r) => (
                  <Link
                    key={r.message_id}
                    to={`/lkml/${encodeURIComponent(r.message_id)}`}
                    className="block p-2.5 rounded-md border border-ink-100 hover:border-ember-500 hover:bg-ember-100/30 transition-all"
                  >
                    <div className="text-sm font-medium text-ink-900 line-clamp-2">
                      {r.subject}
                    </div>
                    <div className="text-xs text-ink-500 mt-1 flex items-center justify-between gap-2">
                      <span className="truncate">{r.author}</span>
                      <span className="shrink-0">{formatDateTime(r.date)}</span>
                    </div>
                    {r.is_patch && (
                      <Tag color="orange" className="!mt-1 !text-xs">
                        PATCH
                      </Tag>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
