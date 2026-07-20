import { useCallback, useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  DatePicker,
  Empty,
  Modal,
  Pagination,
  Spin,
  Tag,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import { dailyApi } from "@/api/daily";
import { formatDate } from "@/utils/format";
import type { DailyArticle } from "@/types";

const PAGE_SIZE = 12;
type RangeValue = [Dayjs | null, Dayjs | null] | null;

export default function DailyList() {
  const { message } = App.useApp();
  const [items, setItems] = useState<DailyArticle[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<RangeValue>(null);

  const [regenOpen, setRegenOpen] = useState(false);
  const [regenDate, setRegenDate] = useState<Dayjs | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Parameters<typeof dailyApi.list>[0] = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format("YYYY-MM-DD");
        params.date_to = dateRange[1].format("YYYY-MM-DD");
      }
      const resp = await dailyApi.list(params);
      setItems(resp.items);
      setTotal(resp.total);
    } finally {
      setLoading(false);
    }
  }, [page, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const dateStr = regenDate ? regenDate.format("YYYY-MM-DD") : undefined;
      const resp = await dailyApi.regenerate(dateStr);
      message.success(`已重新生成：${resp.title}`);
      setRegenOpen(false);
      setRegenDate(null);
      setPage(1);
      fetchData();
    } catch {
      // 接口异常已由拦截器提示
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900 m-0">
            每日技术文章
          </h1>
          <p className="text-ink-500 text-sm mt-1">
            基于 LKML 邮件自动生成的每日技术摘要
          </p>
        </div>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => setRegenOpen(true)}
          type="primary"
          className="lk-btn-ember"
        >
          重新生成
        </Button>
      </div>

      <Card variant="borderless" className="lk-card">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-ink-500 text-sm">日期范围</span>
          <DatePicker.RangePicker
            value={dateRange}
            onChange={(v) => {
              setDateRange(v);
              setPage(1);
            }}
            placeholder={["开始日期", "结束日期"]}
          />
          {dateRange && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                setDateRange(null);
                setPage(1);
              }}
            >
              清除筛选
            </Button>
          )}
        </div>
      </Card>

      <Spin spinning={loading}>
        {items.length === 0 && !loading ? (
          <Card variant="borderless" className="lk-card">
            <Empty description="暂无文章" />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((a) => (
              <Card
                key={a.id}
                variant="borderless"
                className="lk-card hover:shadow-cardHover transition-all h-full flex flex-col"
              >
                <div className="text-xs text-ember-600 font-display font-semibold tracking-wide uppercase">
                  {formatDate(a.date)}
                </div>
                <h3 className="font-display font-semibold text-ink-900 text-base mt-1 mb-2 line-clamp-2 min-h-[48px]">
                  {a.title}
                </h3>
                <p className="text-sm text-ink-600 leading-relaxed line-clamp-2 flex-1">
                  {a.summary || "(无摘要)"}
                </p>
                {a.subsystems && a.subsystems.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {a.subsystems.slice(0, 4).map((s) => (
                      <Tag key={s} color="blue" className="!text-xs !m-0">
                        {s}
                      </Tag>
                    ))}
                  </div>
                )}
                <div className="mt-3 pt-3 border-t border-ink-100">
                  <Link to={`/daily/${a.id}`}>
                    <Button type="link" size="small" className="!px-0">
                      阅读全文 →
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>

      {total > PAGE_SIZE && (
        <div className="flex justify-center pt-2">
          <Pagination
            current={page}
            pageSize={PAGE_SIZE}
            total={total}
            onChange={setPage}
            showTotal={(t) => `共 ${t} 篇文章`}
            disabled={loading}
          />
        </div>
      )}

      <Modal
        open={regenOpen}
        title="重新生成每日文章"
        onCancel={() => setRegenOpen(false)}
        onOk={handleRegenerate}
        confirmLoading={regenerating}
        okText="开始生成"
        cancelText="取消"
        destroyOnHidden
      >
        <div className="py-2">
          <p className="text-ink-500 text-sm mb-3">
            选择需要重新生成的日期（留空则重新生成今日文章）。
          </p>
          <DatePicker
            value={regenDate}
            onChange={setRegenDate}
            style={{ width: "100%" }}
            placeholder="选择日期（可选）"
          />
        </div>
      </Modal>
    </div>
  );
}
