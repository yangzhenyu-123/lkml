import { useState } from "react";
import { Card, Input, Button, Tag, App, Space, Typography } from "antd";
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { opencodeApi } from "@/api/opencode";
import type { OpenCodeTestResult } from "@/types";

const { Text } = Typography;

export default function TestTab() {
  const { message } = App.useApp();
  const [prompt, setPrompt] = useState("Hello, please respond with OK.");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OpenCodeTestResult | null>(null);

  const runTest = async () => {
    setLoading(true);
    setResult(null);
    try {
      const r = await opencodeApi.test({ prompt });
      setResult(r);
      if (r.success) {
        message.success(`测试成功（${r.duration_ms} ms）`);
      } else {
        message.error("测试失败");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="lk-card" variant="borderless">
        <p className="text-sm text-ink-600 mb-3">
          用于验证 OpenCode 配置是否可用。点击运行测试将以当前配置发起一次模型调用。
        </p>
        <Input.TextArea
          rows={4}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="请输入测试 prompt"
        />
        <div className="mt-3">
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runTest}
            className="lk-btn-ember"
          >
            运行测试
          </Button>
        </div>
      </Card>

      {result && (
        <Card
          className="lk-card"
          variant="borderless"
          title={
            <Space>
              <span className="font-display font-semibold">测试结果</span>
              {result.success ? (
                <Tag icon={<CheckCircleOutlined />} color="success">
                  成功
                </Tag>
              ) : (
                <Tag icon={<ExclamationCircleOutlined />} color="error">
                  失败
                </Tag>
              )}
            </Space>
          }
          extra={<Text type="secondary">耗时 {result.duration_ms} ms</Text>}
        >
          {result.error && (
            <div className="mb-3 p-3 rounded bg-red-50 text-red-700 text-sm">
              {result.error}
            </div>
          )}
          <pre className="bg-ink-900 text-ink-100 p-4 rounded-lg overflow-x-auto text-sm mono whitespace-pre-wrap">
            {result.output || "（无输出）"}
          </pre>
        </Card>
      )}
    </div>
  );
}
