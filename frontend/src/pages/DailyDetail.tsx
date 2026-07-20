import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Descriptions,
  Empty,
  Space,
  Spin,
  Tag,
} from "antd";
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { dailyApi } from "@/api/daily";
import { formatDate, formatDateTime } from "@/utils/format";
import type { DailyArticle } from "@/types";

export default function DailyDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();

  const [article, setArticle] = useState<DailyArticle | null>(null);
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    if (!id) return;
    const numId = parseInt(id, 10);
    if (Number.isNaN(numId)) return;
    setLoading(true);
    setContentLoading(true);
    (async () => {
      try {
        const data = await dailyApi.detail(numId);
        setArticle(data);
        const c = await dailyApi.content(numId);
        setContent(c || "");
      } finally {
        setLoading(false);
        setContentLoading(false);
      }
    })();
  }, [id]);

  const handleRegenerate = async () => {
    if (!article) return;
    setRegenerating(true);
    try {
      const resp = await dailyApi.regenerate(article.date);
      message.success(`已重新生成：${resp.title}`);
      setArticle(resp);
      const c = await dailyApi.content(resp.id);
      setContent(c || "");
    } catch {
      // 接口异常已由拦截器提示
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  if (!article) {
    return <Empty description="未找到该文章" />;
  }

  const relatedEmails = (article.email_ids || []).slice(0, 5);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-ember-600 font-display font-semibold tracking-wide uppercase">
            {formatDate(article.date)}
          </div>
          <h1 className="font-display text-2xl font-bold text-ink-900 m-0 break-words">
            {article.title}
          </h1>
          {article.subsystems && article.subsystems.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {article.subsystems.map((s) => (
                <Tag key={s} color="blue" className="!text-xs !m-0">
                  {s}
                </Tag>
              ))}
            </div>
          )}
        </div>
        <Button
          icon={<ReloadOutlined />}
          onClick={handleRegenerate}
          loading={regenerating}
          type="primary"
          className="lk-btn-ember"
        >
          重新生成
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card variant="borderless" className="lk-card">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="创建时间">
                {formatDateTime(article.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="包含邮件数">
                <Space>
                  <FileTextOutlined className="text-ember-500" />
                  <span className="font-display font-semibold text-ink-900">
                    {article.email_ids?.length || 0}
                  </span>
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="正文" variant="borderless" className="lk-card">
            {contentLoading ? (
              <div className="py-12 text-center">
                <Spin />
              </div>
            ) : content ? (
              <div className="lk-markdown">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                >
                  {content}
                </ReactMarkdown>
              </div>
            ) : (
              <Empty description="暂无正文内容" />
            )}
          </Card>
        </div>

        <div>
          <Card
            title="相关邮件"
            variant="borderless"
            className="lk-card sticky top-4"
          >
            {relatedEmails.length === 0 ? (
              <Empty description="无关联邮件" />
            ) : (
              <div className="space-y-2">
                {relatedEmails.map((mid, i) => (
                  <Link
                    key={`${mid}-${i}`}
                    to={`/lkml/${encodeURIComponent(mid)}`}
                    className="block p-2.5 rounded-md border border-ink-100 hover:border-ember-500 hover:bg-ember-100/30 transition-all"
                  >
                    <div className="text-xs text-ink-400">#{i + 1}</div>
                    <div className="text-sm font-mono text-ink-700 truncate">
                      {mid}
                    </div>
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
