import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Button, Tag, Empty, Spin, Progress } from "antd";
import {
  MailOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  ArrowRightOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { statsApi } from "@/api/stats";
import { historyApi } from "@/api/history";
import { dailyApi } from "@/api/daily";
import { stageMeta, jobStatusMap, fromNow } from "@/utils/format";
import type { AnalysisJob, DailyArticle } from "@/types";

interface Stats {
  emailCount: number;
  jobCount: number;
  articleCount: number;
  retryPending: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentJobs, setRecentJobs] = useState<AnalysisJob[]>([]);
  const [recentArticles, setRecentArticles] = useState<DailyArticle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // 用专用 stats 接口获取计数（单次 DB 往返），避免 3 个 list 各做 COUNT(*)
        const [s, jobs, articles] = await Promise.all([
          statsApi.dashboard(),
          historyApi.list({ limit: 5 }),
          dailyApi.list({ limit: 5 }),
        ]);
        setStats({
          emailCount: s.email_count,
          jobCount: s.job_count,
          articleCount: s.article_count,
          retryPending: s.retry_pending,
        });
        setRecentJobs(jobs.items);
        setRecentArticles(articles.items);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      <Card variant="borderless" className="!bg-ink-900 !border-none overflow-hidden relative">
        <div
          className="absolute top-0 right-0 w-72 h-72 rounded-full opacity-20 blur-3xl"
          style={{ background: "#FF6B35", transform: "translate(30%, -40%)" }}
        />
        <div className="relative z-10 py-4">
          <h1 className="!text-white font-display text-2xl font-bold mb-2">
            内核性能优化专利挖掘工作台
          </h1>
          <p className="text-ink-200 text-sm max-w-2xl">
            从 LKML 历史邮件中识别未合入的性能优化提案，借助 OpenCode 与
            patent-disclosure-skill 生成改进方案与中国专利技术交底书。
          </p>
          <Link to="/history">
            <Button type="primary" className="lk-btn-ember mt-4">
              发起新分析任务 <ArrowRightOutlined />
            </Button>
          </Link>
        </div>
      </Card>

      {/* 统计卡 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="lk-card">
            <Statistic
              title={<span className="text-ink-500 text-xs">邮件总数</span>}
              value={stats.emailCount}
              prefix={<MailOutlined className="text-ember-500" />}
              valueStyle={{ color: "#0B1F3A", fontFamily: "Sora" }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="lk-card">
            <Statistic
              title={<span className="text-ink-500 text-xs">历史分析任务</span>}
              value={stats.jobCount}
              prefix={<ApartmentOutlined className="text-stage-s2" />}
              valueStyle={{ color: "#0B1F3A", fontFamily: "Sora" }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="lk-card">
            <Statistic
              title={<span className="text-ink-500 text-xs">每日文章</span>}
              value={stats.articleCount}
              prefix={<FileTextOutlined className="text-stage-s4" />}
              valueStyle={{ color: "#0B1F3A", fontFamily: "Sora" }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="lk-card">
            <Statistic
              title={<span className="text-ink-500 text-xs">失败任务待重试</span>}
              value={stats.retryPending}
              prefix={<ClockCircleOutlined className="text-ember-600" />}
              valueStyle={{ color: "#E5532A", fontFamily: "Sora" }}
            />
          </Card>
        </Col>
      </Row>

      {/* 流水线概览 */}
      <Card
        title={<span className="font-display font-semibold">4 阶段流水线</span>}
        variant="borderless"
        className="lk-card"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {stageMeta.map((s, idx) => (
            <div key={s.no} className="relative">
              <div className={`p-4 rounded-lg bg-${s.color}/10 border border-${s.color}/30`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">{s.icon}</span>
                  <div>
                    <div className="text-xs text-ink-500">阶段 {s.no}</div>
                    <div className={`font-display font-semibold text-${s.color}`}>{s.name}</div>
                  </div>
                </div>
                <p className="text-xs text-ink-600 leading-relaxed">{s.desc}</p>
                {s.retryable && (
                  <Tag color="orange" className="mt-2 !text-xs">
                    可重试
                  </Tag>
                )}
              </div>
              {idx < 3 && (
                <ArrowRightOutlined className="hidden md:block absolute top-1/2 -right-3 -translate-y-1/2 text-ink-300 z-10 bg-paper px-1" />
              )}
            </div>
          ))}
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        {/* 最近任务 */}
        <Col xs={24} md={14}>
          <Card
            title={<span className="font-display font-semibold">最近分析任务</span>}
            variant="borderless"
            className="lk-card"
            extra={
              <Link to="/history">
                <Button type="link" size="small">
                  查看全部
                </Button>
              </Link>
            }
          >
            {recentJobs.length === 0 ? (
              <Empty description="暂无任务" />
            ) : (
              <div className="space-y-2">
                {recentJobs.map((job) => {
                  const sm = jobStatusMap[job.status];
                  return (
                    <Link
                      key={job.id}
                      to={`/history/${job.id}`}
                      className="block p-3 rounded-md border border-ink-100 hover:border-ember-500 hover:bg-ember-100/30 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-ink-900 truncate">{job.name}</div>
                          <div className="text-xs text-ink-500 mt-0.5">
                            {job.year_start} - {job.year_end} · {fromNow(job.created_at)}
                          </div>
                        </div>
                        <Tag color={sm.color}>{sm.text}</Tag>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>

        {/* 最近文章 */}
        <Col xs={24} md={10}>
          <Card
            title={<span className="font-display font-semibold">最近每日文章</span>}
            variant="borderless"
            className="lk-card"
            extra={
              <Link to="/daily">
                <Button type="link" size="small">
                  查看全部
                </Button>
              </Link>
            }
          >
            {recentArticles.length === 0 ? (
              <Empty description="暂无文章" />
            ) : (
              <div className="space-y-2">
                {recentArticles.map((a) => (
                  <Link
                    key={a.id}
                    to={`/daily/${a.id}`}
                    className="block p-3 rounded-md border border-ink-100 hover:border-ember-500 hover:bg-ember-100/30 transition-all"
                  >
                    <div className="font-medium text-ink-900 line-clamp-1">{a.title}</div>
                    <div className="text-xs text-ink-500 mt-0.5">{a.date}</div>
                    {a.subsystems?.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {a.subsystems.slice(0, 4).map((s) => (
                          <Tag key={s} className="!text-xs !m-0">
                            {s}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
