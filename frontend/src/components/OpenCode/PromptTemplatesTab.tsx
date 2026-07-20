import { useEffect, useState } from "react";
import { Card, Form, Input, Button, App, Tag } from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { opencodeApi } from "@/api/opencode";
import type { OpenCodeConfig } from "@/types";

const STAGE3_VARS = ["{{proposal}}", "{{context}}", "{{subsystem}}"];
const STAGE4_VARS = [
  "{{proposal}}",
  "{{optimization}}",
  "{{subsystem}}",
  "{{context}}",
];

interface PromptValues {
  stage3: string;
  stage4: string;
}

export default function PromptTemplatesTab({
  config,
  onUpdated,
}: {
  config: OpenCodeConfig;
  onUpdated: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<PromptValues>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    form.setFieldsValue({
      stage3: config.prompt_templates?.stage3 ?? "",
      stage4: config.prompt_templates?.stage4 ?? "",
    });
  }, [config, form]);

  const handleSave = async (values: PromptValues) => {
    setSaving(true);
    try {
      await opencodeApi.updateConfig({
        prompt_templates: {
          stage3: values.stage3,
          stage4: values.stage4,
        },
      });
      message.success("提示词模板已保存");
      onUpdated();
    } finally {
      setSaving(false);
    }
  };

  const renderVars = (vars: string[]) => (
    <div className="mb-4 flex flex-wrap items-center gap-1">
      <span className="text-xs text-ink-500 mr-1">可用变量：</span>
      {vars.map((v) => (
        <Tag key={v} className="!text-xs !m-0 font-mono">
          {v}
        </Tag>
      ))}
    </div>
  );

  return (
    <Card className="lk-card" variant="borderless">
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item
          label={
            <span className="font-medium">
              Stage 3 · 优化方案 Prompt
            </span>
          }
          name="stage3"
        >
          <Input.TextArea
            rows={10}
            showCount
            placeholder="请输入 Stage 3 优化方案阶段的提示词模板..."
          />
        </Form.Item>
        {renderVars(STAGE3_VARS)}

        <Form.Item
          label={
            <span className="font-medium">
              Stage 4 · 专利提取 Prompt
            </span>
          }
          name="stage4"
        >
          <Input.TextArea
            rows={10}
            showCount
            placeholder="请输入 Stage 4 专利提取阶段的提示词模板..."
          />
        </Form.Item>
        {renderVars(STAGE4_VARS)}

        <div className="mt-2">
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined />}
            loading={saving}
            className="lk-btn-ember"
          >
            保存模板
          </Button>
        </div>
      </Form>
    </Card>
  );
}
